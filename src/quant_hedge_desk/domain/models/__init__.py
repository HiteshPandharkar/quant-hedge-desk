"""Immutable domain dataclasses grouped by bounded context."""

from quant_hedge_desk.domain.errors import (
    DealerRiskValidationError,
    DecisionValidationError,
    InstrumentValidationError,
)
from quant_hedge_desk.domain.models.decision_models import (
    CandidateDecisionDiagnostic,
    CandidateDecisionInput,
    PreTradeDecisionResult,
)
from quant_hedge_desk.domain.models.dealer_risk_models import (
    DealerRiskAssessment,
    ProposedTradeRisk,
    RiskLimitDiagnostic,
)
from quant_hedge_desk.domain.enums import (
    CandidateRelationship,
    PreTradeDecision,
    RiskLimitStatus,
)
from quant_hedge_desk.domain.models.desk_limits import DealerRiskLimits, DeskLimitSet
from quant_hedge_desk.domain.models.desk_portfolio import (
    DeskPortfolio,
    DeskPortfolioValidationError,
    DeskPosition,
    DeskRiskExposure,
)
from quant_hedge_desk.domain.models.derivative_legs import (
    FutureLeg,
    FuturesLeg,
    OptionLeg,
    VanillaOptionLeg,
)
from quant_hedge_desk.domain.models.mandate import (
    ClientMandate,
    CostConstraint,
    EligibilityConstraint,
    LiquidityConstraint,
    Mandate,
    ProtectionConstraint,
    RebalancingPolicy,
    RequirementInterpretation,
    UpsideConstraint,
)
from quant_hedge_desk.domain.models.portfolio import Portfolio, PortfolioHolding
from quant_hedge_desk.domain.models.scenario_contracts import (
    Scenario,
    ScenarioPath,
    ScenarioSet,
    ScenarioStep,
)
from quant_hedge_desk.domain.models.scenario_outcomes import (
    ScenarioEvaluation,
    ScenarioOutcome,
)

__all__ = [
    "CandidateDecisionDiagnostic",
    "CandidateDecisionInput",
    "CandidateRelationship",
    "ClientMandate",
    "CostConstraint",
    "DealerRiskAssessment",
    "DealerRiskValidationError",
    "DecisionValidationError",
    "DealerRiskLimits",
    "DeskLimitSet",
    "DeskPortfolio",
    "DeskPortfolioValidationError",
    "DeskPosition",
    "DeskRiskExposure",
    "EligibilityConstraint",
    "FutureLeg",
    "FuturesLeg",
    "InstrumentValidationError",
    "LiquidityConstraint",
    "Mandate",
    "OptionLeg",
    "Portfolio",
    "PortfolioHolding",
    "PreTradeDecision",
    "PreTradeDecisionResult",
    "ProtectionConstraint",
    "ProposedTradeRisk",
    "RebalancingPolicy",
    "RequirementInterpretation",
    "RiskLimitDiagnostic",
    "RiskLimitStatus",
    "Scenario",
    "ScenarioEvaluation",
    "ScenarioOutcome",
    "ScenarioPath",
    "ScenarioSet",
    "ScenarioStep",
    "UpsideConstraint",
    "VanillaOptionLeg",
]
