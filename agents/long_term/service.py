"""Internal service and scheduler entry point; never wires brokers or strategies."""

from datetime import timedelta
from uuid import uuid4

from pydantic import TypeAdapter

from agents.long_term.analysis import evaluate_assumptions, portfolio_context, source_freshness
from agents.long_term.models import (
    Claim,
    Freshness,
    FundamentalData,
    ResearchAssessment,
    ResearchConfig,
    ResearchRun,
    Source,
)
from agents.long_term.valuation import ReportedValuation
from market_data.models import Quote, Symbol
from news.analysis import NewsEvidence
from news.analysis import analyze as analyze_news
from news.thesis_review import NewsReviewInput, news_to_reviews, scheduled_reviews
from portfolio.intelligence import SecurityReference
from portfolio.registry import initial_thesis
from portfolio.theses import PositionThesis


class LongTermResearchAgent:
    def __init__(
        self,
        *,
        store,
        policy,
        market_data=None,
        fundamentals=None,
        news=None,
        references=None,
        valuation=None,
        config=None,
    ):
        self.store = store
        self.policy = policy
        self.market_data = market_data
        self.fundamentals = fundamentals
        self.news = news
        self.references = references
        self.valuation = valuation or ReportedValuation()
        self.config = config or ResearchConfig()

    def canonical(self, symbol):
        symbol = TypeAdapter(Symbol).validate_python(symbol)
        return self.config.aliases.get(symbol, symbol)

    def universe(self, observation_id=None):
        observation = self._observation(observation_id)
        symbols = set(self.policy.research_universe or ())
        if observation:
            symbols.update(p.symbol for p in observation.state.portfolio_holdings)
        return tuple(sorted({self.canonical(s) for s in symbols}))

    def _observation(self, observation_id):
        observation = self.store.portfolio.get(observation_id) if observation_id else None
        if observation_id and observation is None:
            raise ValueError("Portfolio observation not found")
        return observation

    def _theses(self, observation, symbol):
        if observation is None:
            return ()
        keys = sorted(
            {
                (p.account_id, p.symbol)
                for p in observation.state.portfolio_holdings
                if self.canonical(p.symbol) == symbol
            }
        )
        return tuple(
            t
            for account, actual in keys
            if (t := self.store.portfolio.get_thesis(account, actual)) is not None
        )

    def _fetch(self, provider, method, model, symbol, errors):
        if provider is None:
            return None
        try:
            data = model.model_validate(getattr(provider, method)(symbol))
            if data.symbol != symbol:
                raise ValueError("Provider symbol mismatch")
            return data
        except Exception:  # noqa: BLE001 -- sanitize arbitrary adapter failures at trust boundary.
            # Provider exceptions may contain credentials, URLs, or raw private payloads.
            errors.append(method + ":unavailable_or_invalid")
            return None

    def _news_requests(self, news, symbol, scope, theses, now):
        if (
            news is None
            or news.retrieved_at > now
            or (news.is_sample and not self.config.allow_test_data)
        ):
            return (), ()
        if now - news.retrieved_at > timedelta(hours=self.config.news_max_age_hours):
            return (), ()
        analysis = analyze_news(news, now)
        matched = {item for ids in analysis.topics.values() for item in ids}
        # Keyword relevance requests review only; it is never sentiment or verified impact.
        targets = tuple(
            PositionThesis(account_id=t.thesis.account_id, symbol=symbol) for t in theses
        ) or (PositionThesis(account_id=scope, symbol=symbol),)
        requests, event_ids = [], []
        for article in news.articles:
            if article.id not in matched:
                continue
            trigger = (
                "earnings"
                if article.id in analysis.topics.get("earnings", ())
                else "product"
                if article.id in analysis.topics.get("product", ())
                else "regulatory"
                if article.id in analysis.topics.get("regulatory", ())
                else "acquisition_divestiture"
            )
            items = news_to_reviews(
                NewsReviewInput(article=article, trigger=trigger, material=True), targets, now=now
            )
            requests.extend(items)
            event_ids.extend(r.request_id for r in items)
        return tuple(requests), tuple(sorted(set(event_ids)))

    def run(
        self,
        symbol,
        *,
        scope_id,
        now,
        observation_id=None,
        plan=None,
        kind="targeted",
        only_if_due=False,
    ):
        """Trusted local callers provide persisted observation IDs and reviewed plans.

        scope_id must be a stable portfolio/workspace ID, not an observation ID.
        A future API must authenticate and authorize access to that scope.
        """
        if now.tzinfo is None:
            raise ValueError("Research time must be timezone-aware")
        symbol = self.canonical(symbol)
        run = ResearchRun(
            run_id=str(uuid4()),
            timestamp=now,
            scope_id=scope_id,
            symbol=symbol,
            status="STARTED",
            input_snapshot={
                "observation_id": observation_id,
                "policy": self.policy.model_dump(mode="json"),
                "config": self.config.model_dump(mode="json"),
                "plan": plan.model_dump(mode="json") if plan else None,
                "kind": kind,
            },
        )
        self.store.begin(run)
        errors = []
        try:
            if kind not in {"baseline", "targeted", "quarterly"}:
                raise ValueError("Unknown research kind")
            observation = self._observation(observation_id)
            if symbol not in self.universe(observation_id):
                raise ValueError("Symbol outside research universe")
            if observation and observation.state.as_of > now:
                raise ValueError("Future portfolio observation")
            if plan and (plan.symbol != symbol or plan.reviewed_at > now):
                raise ValueError("Invalid research plan scope or timestamp")
            theses = self._theses(observation, symbol)
            previous = self.store.latest(scope_id, symbol)
            if plan is None and previous is not None:
                plan = previous.plan
            run = run.model_copy(
                update={
                    "input_snapshot": run.input_snapshot
                    | {"plan": plan.model_dump(mode="json") if plan else None}
                }
            )
            if previous and previous.timestamp > now:
                raise ValueError("Research timestamp cannot regress")
            run = run.model_copy(
                update={"previous_thesis_state": previous.thesis_status if previous else None}
            )
            quote = self._fetch(self.market_data, "get_quote", Quote, symbol, errors)
            news = self._fetch(self.news, "get_news", NewsEvidence, symbol, errors)
            requests, events = self._news_requests(news, symbol, scope_id, theses, now)
            self.store.portfolio.save_review_requests(requests, news)
            due = scheduled_reviews(tuple(t.thesis for t in theses), now=now)
            self.store.portfolio.save_review_requests(due)
            events = tuple(sorted(set(events + tuple(r.request_id for r in due))))
            fresh_events = tuple(
                e for e in events if not self.store.event_completed(scope_id, symbol, e)
            )
            plan_changed = previous is not None and previous.plan != plan
            retry_due = previous is not None and (
                (
                    previous.thesis_status == "INSUFFICIENT_DATA"
                    and now - previous.timestamp
                    >= timedelta(hours=self.config.incomplete_retry_hours)
                )
                or now - previous.timestamp >= timedelta(days=self.config.full_review_max_age_days)
            )
            if (
                only_if_due
                and previous is not None
                and not fresh_events
                and not plan_changed
                and not retry_due
            ):
                skipped = run.model_copy(
                    update={
                        "status": "SKIPPED",
                        "errors": tuple(errors),
                        "reasoning_summary": "Market/news checked; no new review trigger.",
                        "input_snapshot": run.input_snapshot
                        | {
                            "quote": quote.model_dump(mode="json") if quote else None,
                            "news": news.model_dump(mode="json") if news else None,
                        },
                        "inputs_used": ("market_poll", "news_poll"),
                    }
                )
                self.store.finish(skipped)
                return None
            if (
                any(r.trigger == "earnings" and r.request_id in fresh_events for r in requests)
                or due
            ):
                kind = "quarterly"
            fundamental = self._fetch(
                self.fundamentals, "get_fundamentals", FundamentalData, symbol, errors
            )
            reference = self._fetch(
                self.references, "get_reference", SecurityReference, symbol, errors
            )
            assessment = self._assess(
                symbol,
                scope_id,
                now,
                run.run_id,
                observation,
                theses,
                previous,
                plan,
                kind,
                quote,
                fundamental,
                news,
                reference,
                bool(fresh_events),
            )
            completed = run.model_copy(
                update={
                    "status": "COMPLETED",
                    "assessment_id": assessment.assessment_id,
                    "inputs_used": tuple(
                        name
                        for name, value in (
                            ("market", quote),
                            ("fundamentals", fundamental),
                            ("news", news),
                            ("reference", reference),
                            ("portfolio", observation),
                            ("plan", plan),
                        )
                        if value is not None
                    ),
                    "source_references": tuple(s.source_id for s in assessment.data_sources),
                    "resulting_thesis_state": assessment.thesis_status,
                    "material_changes": assessment.thesis_changes,
                    "missing_information": assessment.missing_data,
                    "errors": tuple(errors),
                    "reasoning_summary": assessment.agent_summary,
                }
            )
            self.store.commit(assessment, completed, theses, fresh_events)
            return assessment
        except Exception as exc:
            self.store.finish(
                run.model_copy(
                    update={
                        "status": "FAILED",
                        "errors": tuple(errors) + (type(exc).__name__,),
                        "reasoning_summary": "Research failed; assessment/thesis transaction not committed.",
                    }
                )
            )
            raise

    def _assess(
        self,
        symbol,
        scope,
        now,
        run_id,
        observation,
        theses,
        previous,
        plan,
        kind,
        quote,
        fundamental,
        news,
        reference,
        triggered,
    ):
        quality, missing, sources, uncertainty = {}, [], [], []
        for name, item, stamp, hours in (
            ("market", quote, quote.as_of if quote else None, self.config.market_max_age_hours),
            ("news", news, news.retrieved_at if news else None, self.config.news_max_age_hours),
        ):
            usable = (
                item is not None
                and stamp <= now
                and (not item.is_sample or self.config.allow_test_data)
            )
            state = (
                "UNAVAILABLE"
                if not usable
                else "STALE"
                if now - stamp > timedelta(hours=hours)
                else "CURRENT"
            )
            quality[name] = Freshness(state=state, as_of=stamp)
            if state != "CURRENT":
                missing.append(name + ":" + state.lower())
        if quote:
            sources.append(
                Source(
                    source_id="market:quote",
                    symbol=symbol,
                    source=quote.source,
                    source_type="market_data",
                    published_at=quote.as_of,
                    retrieved_at=max(now, quote.as_of),
                    relevant_claim="Observed price",
                    reliable=True,
                    is_sample=quote.is_sample,
                )
            )
        if news:
            sources.extend(
                Source(
                    source_id="news:" + a.id,
                    symbol=symbol,
                    source=a.publisher,
                    source_type="news",
                    published_at=a.published_at,
                    retrieved_at=news.retrieved_at,
                    relevant_claim=a.headline,
                    url=str(a.url),
                    is_sample=news.is_sample,
                )
                for a in news.articles
            )
        eligible, usable_claims = (), {}
        if fundamental:
            reserved = {s.source_id for s in sources}
            if any(s.source_id in reserved for s in fundamental.sources):
                raise ValueError("Source ID collision")
            sources.extend(fundamental.sources)
            for source in fundamental.sources:
                quality[source.source_id] = source_freshness(source, now, self.config)
            bundle_ok = fundamental.retrieved_at <= now
            usable_ids = (
                {sid for sid, q in quality.items() if q.state == "LATEST_REPORTED"}
                if bundle_ok
                else set()
            )
            historical_ids = {sid for sid, q in quality.items() if q.state == "HISTORICAL"}
            eligible = tuple(m for m in fundamental.metrics if m.source_id in usable_ids)
            for category, claims in fundamental.claims.items():
                usable_claims[category] = tuple(
                    c
                    for c in claims
                    if set(c.evidence_references) <= usable_ids | historical_ids
                    and set(c.evidence_references) & usable_ids
                )
            for source in fundamental.sources:
                if quality[source.source_id].state in {"STALE", "UNAVAILABLE"}:
                    missing.append(
                        "source:" + source.source_id + ":" + quality[source.source_id].state.lower()
                    )
            if not bundle_ok:
                missing.append("fundamentals:future_retrieval")
        if not eligible:
            missing.append("fundamental_metrics")
        quality["fundamentals"] = Freshness(
            state="LATEST_REPORTED" if eligible else "UNAVAILABLE",
            as_of=max(
                (s.published_at for s in sources if s.source_id in {m.source_id for m in eligible}),
                default=None,
            ),
        )
        periods = {(m.period_start, m.period_end, m.basis) for m in eligible}
        if len(periods) > 1:
            uncertainty.append(
                "Multiple metric periods/bases retained separately; no blended valuation or growth comparison."
            )
        status, results, positives, negatives, gaps = evaluate_assumptions(plan, eligible, previous)
        missing.extend(gaps)
        if triggered and status in {"UNCHANGED", "STRONGER"}:
            status = "UNDER_REVIEW"
        source_map = {s.source_id: s for s in sources}
        valuation_metrics = tuple(
            m
            for m in eligible
            if now - source_map[m.source_id].published_at
            <= timedelta(days=self.config.valuation_max_age_days)
        )
        valuation = self.valuation.analyze(valuation_metrics)
        if any(m not in valuation_metrics for m in valuation.methods) or any(
            not set(c.evidence_references) <= {m.source_id for m in valuation_metrics}
            for c in valuation.conclusions
        ):
            raise ValueError("Valuation returned unsupported evidence")
        if valuation.status == "INSUFFICIENT_DATA":
            missing.append("valuation")
        context = portfolio_context(observation, symbol, self.canonical, theses)
        if context:
            quality["portfolio"] = Freshness(
                state="STALE"
                if now - context.as_of > timedelta(hours=self.config.market_max_age_hours)
                else "CURRENT",
                as_of=context.as_of,
            )
            missing.extend("portfolio:" + gap for gap in context.data_gaps)
            if quality["portfolio"].state == "STALE":
                missing.append("portfolio:stale")
        else:
            missing.append("portfolio_context")
        valid_reference = (
            reference and reference.verified and reference.as_of <= now <= reference.valid_until
        )
        if not valid_reference:
            missing.append("reference_data")
        if not theses:
            missing.append("position_thesis")
        for name in (
            "business_summary",
            "growth_context",
            "profitability_context",
            "financial_health",
            "competitive_position",
            "ai_exposure",
            "cash_generation",
            "catalysts",
            "risks",
        ):
            if not usable_claims.get(name):
                missing.append(name)
        changes = []
        if previous:
            if previous.plan != plan:
                changes.append("Reviewed research plan changed; directional comparison reset.")
            for key, value in results.items():
                if previous.assumption_results.get(key) != value:
                    changes.append(
                        f"Assumption {key}: {previous.assumption_results.get(key)} -> {value}"
                    )
            previous_metrics = {(m.name, m.unit, m.basis): m for m in previous.metrics}
            for metric in eligible:
                old = previous_metrics.get((metric.name, metric.unit, metric.basis))
                if old and (old.value, old.period_end) != (metric.value, metric.period_end):
                    changes.append(
                        f"Metric {metric.name}: {old.value} ({old.period_end}) -> {metric.value} ({metric.period_end}); separate reported periods."
                    )
        if triggered:
            changes.append(
                "New material-topic or scheduled review request; impact requires corroboration."
            )
        if any(s.is_sample for s in sources):
            uncertainty.append(
                "Synthetic evidence present; test mode only, not investment evidence."
            )
        uncertainty.extend(
            (
                "Source reliability is adapter-attested, not independently verified.",
                "Thesis direction and portfolio sizing risk are separate; no trading recommendation.",
                "ETF look-through and diversification impact are unknown without additional evidence.",
            )
        )
        defaults = (
            [
                initial_thesis("research", p.symbol)
                for p in observation.state.portfolio_holdings
                if self.canonical(p.symbol) == symbol
            ]
            if observation
            else []
        )
        roles = tuple(
            sorted(
                {
                    t.portfolio_role
                    for t in [*(s.thesis for s in theses), *defaults]
                    if t.portfolio_role
                }
            )
        )
        fields = {
            name: usable_claims.get(name, ())
            for name in (
                "business_summary",
                "financial_health",
                "growth_context",
                "profitability_context",
                "competitive_position",
                "ai_exposure",
                "cash_generation",
                "risks",
                "catalysts",
            )
        }
        if news and quality["news"].state == "CURRENT":
            fields["catalysts"] += tuple(
                Claim(
                    text=f"Unverified {c.certainty} catalyst: {c.title}; {c.event_at.isoformat()}",
                    evidence_references=("news:" + c.evidence_id,),
                    kind="interpretation",
                )
                for c in news.catalysts
                if c.event_at >= now
            )
        summary = f"{status}: evaluated {len(results)} reviewed assumptions; {len(missing)} missing/stale input categories. Research only."
        return ResearchAssessment(
            run_id=run_id,
            scope_id=scope,
            symbol=symbol,
            timestamp=now,
            research_horizon=self.policy.holding_horizon,
            portfolio_role=roles,
            thesis_reference=tuple(
                f"thesis:{t.thesis.account_id}:{t.thesis.symbol}:{t.revision}" for t in theses
            ),
            previous_assessment_id=previous.assessment_id if previous else None,
            current_price=quote.price if quote and quality["market"].state == "CURRENT" else None,
            price_currency=quote.currency if quote else None,
            market_data_timestamp=quote.as_of if quote else None,
            fundamental_data_timestamp=quality["fundamentals"].as_of,
            investment_thesis=plan.thesis if plan else None,
            thesis_status=status,
            thesis_changes=tuple(changes),
            positive_drivers=positives,
            negative_drivers=negatives,
            invalidation_conditions=tuple(
                a.name for a in plan.assumptions if a.invalidates_when_false
            )
            if plan
            else (),
            valuation_context=valuation,
            portfolio_fit=context,
            concentration_impact=context.concentration_flags if context else (),
            relevant_news=news,
            data_sources=tuple(sources),
            data_quality=quality,
            missing_data=tuple(sorted(set(missing))),
            uncertainty=tuple(uncertainty),
            agent_summary=summary,
            metrics=eligible,
            assumption_results=results,
            plan=plan,
            quote=quote,
            fundamental_data=fundamental,
            reference_data=reference.model_dump(mode="json") if reference else None,
            review_kind=kind,
            **fields,
        )

    def daily_cycle(self, *, scope_id, now, observation_id=None, plans=None):
        results = {}
        for symbol in self.universe(observation_id):
            try:
                results[symbol] = self.run(
                    symbol,
                    scope_id=scope_id,
                    now=now,
                    observation_id=observation_id,
                    plan=(plans or {}).get(symbol),
                    only_if_due=True,
                )
            except Exception:  # noqa: BLE001 -- isolate symbol failures; run() retains durable audit.
                results[symbol] = None  # Durable FAILED run distinguishes failures from skips.
        return results

    def quarterly_review(self, symbol, **kwargs):
        return self.run(symbol, kind="quarterly", **kwargs)

    def compare(self, *, scope_id):
        """Comparable records, canonical symbol order, no ranking or winner."""
        return tuple(
            {"symbol": symbol, "assessment": self.store.latest(scope_id, symbol)}
            for symbol in sorted({self.canonical(s) for s in self.config.comparison_symbols})
        )
