import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from trading.models import (
    ApprovalInput,
    AutomationPolicyInput,
    AutomationQualificationInput,
    KillSwitchInput,
    ProposalInput,
)
from trading.service import TradeConflict


def trading_router(service, settings):
    router = APIRouter(prefix="/trading", tags=["Human-approved synthetic trading"])

    def authenticate(authorization, expected):
        if not authorization or not secrets.compare_digest(
            authorization, "Bearer " + expected.get_secret_value()
        ):
            raise HTTPException(401, "Invalid trading credential")

    def agent(authorization: str | None = Header(default=None)):
        authenticate(authorization, settings.trading_agent_token)

    def human(authorization: str | None = Header(default=None)):
        authenticate(authorization, settings.trading_approval_token)

    def reader(authorization: str | None = Header(default=None)):
        for token in (settings.trading_agent_token, settings.trading_approval_token):
            if authorization and secrets.compare_digest(
                authorization, "Bearer " + token.get_secret_value()
            ):
                return
        raise HTTPException(401, "Invalid trading credential")

    def call(function, *args):
        try:
            return function(*args)
        except KeyError:
            raise HTTPException(404, "Proposal not found") from None
        except TradeConflict as exc:
            raise HTTPException(409, str(exc)) from None
        except SQLAlchemyError:
            raise HTTPException(503, "Trading storage unavailable") from None

    @router.post("/proposals", status_code=201, dependencies=[Depends(agent)])
    def propose(inputs: ProposalInput):
        return call(service.propose, inputs)

    @router.get("/proposals/{proposal_id}", dependencies=[Depends(reader)])
    def get(proposal_id: UUID):
        proposal = call(service.get, proposal_id)
        if proposal is None:
            raise HTTPException(404, "Proposal not found")
        return proposal

    @router.post("/proposals/{proposal_id}/approve", dependencies=[Depends(human)])
    def approve(proposal_id: UUID, approval: ApprovalInput):
        return call(service.transition, proposal_id, "approve", approval.digest)

    @router.post("/proposals/{proposal_id}/reject", dependencies=[Depends(human)])
    def reject(proposal_id: UUID):
        return call(service.transition, proposal_id, "reject")

    @router.post("/proposals/{proposal_id}/execute", dependencies=[Depends(agent)])
    def execute(proposal_id: UUID):
        return call(service.transition, proposal_id, "execute")

    @router.put("/kill-switch", dependencies=[Depends(human)])
    def kill(request: KillSwitchInput):
        return call(service.kill, request.enabled)

    @router.get("/account", dependencies=[Depends(reader)])
    def account():
        return call(service.account)

    @router.get("/audit", dependencies=[Depends(human)])
    def audit():
        return call(service.audit)

    @router.post("/reconcile", dependencies=[Depends(human)])
    def reconcile():
        return call(service.reconcile)

    @router.put("/automation/policy", dependencies=[Depends(human)])
    def register_automation_policy(request: AutomationPolicyInput):
        return call(service.register_automation_policy, request)

    @router.post("/automation/qualification", dependencies=[Depends(human)])
    def qualify_automation(request: AutomationQualificationInput):
        return call(
            service.qualify_automation,
            request.backtest_id,
            request.paper_run_id,
        )

    @router.get("/automation/status", dependencies=[Depends(reader)])
    def automation_status():
        return call(service.automation_status)

    return router
