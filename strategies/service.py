"""Trusted internal workflow: assessment -> opportunity -> strategy -> risk -> stop."""

from portfolio.intelligence import experimental_utilization
from risk.evaluator import digest
from strategies.dispatch import strategy_for
from strategies.opportunities import OpportunityEngine
from strategies.review import review_strategy_proposal


class OpportunityStrategyService:
    def __init__(self, store):
        self.store = store

    def run(
        self,
        assessment,
        thesis,
        opening,
        state,
        policy,
        version,
        kill_switch,
        *,
        now,
        fees=None,
        history=None,
        validation=None,
    ):
        self.store.register(version)
        opportunity = OpportunityEngine().identify(
            assessment,
            thesis,
            state,
            policy,
            version.configuration,
            now=now,
            domain=version.strategy_domain,
        )
        strategy = strategy_for(version)
        evaluation = strategy.evaluate(
            opportunity,
            assessment,
            thesis,
            state,
            policy,
            version,
            now=now,
            fees=fees,
            history=history,
        )
        review = None
        if evaluation.proposal:
            review = review_strategy_proposal(
                policy,
                opening,
                state,
                evaluation.proposal,
                kill_switch,
                thesis,
                opportunity,
                assessment,
                version,
                now=now,
                history=history,
                validation=validation,
            )
        events = []

        def event(name, status, reasons=()):
            events.append(
                {
                    "event": name,
                    "timestamp": now.isoformat(),
                    "correlation_id": opportunity.opportunity_id,
                    "strategy_id": version.strategy_id,
                    "strategy_version": version.strategy_version,
                    "status": status,
                    "reasons": list(reasons),
                    "execution_available": False,
                }
            )

        event("opportunity_created", opportunity.opportunity_status, opportunity.missing_data)
        event("strategy_evaluated", evaluation.status, evaluation.reasons)
        if review:
            event("proposal_created", evaluation.proposal.status)
            event(
                "risk_evaluated",
                review.status,
                review.reasons + tuple(c.code for c in review.risk.checks if not c.passed),
            )
            event(
                "human_review_required"
                if review.status == "REQUIRE_HUMAN_REVIEW"
                else "proposal_blocked",
                review.status,
                review.reasons,
            )
        inputs = {
            "assessment": assessment,
            "thesis": thesis,
            "opening": opening,
            "state": state,
            "policy": policy,
            "version": version,
            "kill_switch": kill_switch,
            "history": history,
            "validation": validation,
        }
        bundle = {
            "opportunity": opportunity.model_dump(mode="json"),
            "evaluation": evaluation.model_dump(mode="json"),
            "review": review.model_dump(mode="json") if review else None,
            "inputs": {
                k: v.model_dump(mode="json") if v is not None else None for k, v in inputs.items()
            },
            "input_digest": digest(inputs),
            "fees": str(fees) if fees is not None else None,
            "evaluated_at": now.isoformat(),
            "experimental_capital": experimental_utilization(state, policy).model_dump(mode="json"),
            "events": events,
        }
        self.store.save(opportunity, bundle)
        return bundle
