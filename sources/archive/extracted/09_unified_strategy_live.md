# SEP Unified Strategy: Production Deployment

**Document Version:** 1.0  
**Date:** December 7, 2025  
**Status:** Production Ready  
**Classification:** Internal - Stakeholder Review

---

## Executive Summary

This whitepaper documents the complete journey of the SEP Trading System from a failing $-10.51 Iron Dome architecture to a production-ready unified strategy achieving **50% win rate** and **$845 projected 3-month P&L**. 

The unified approach fundamentally reconceptualizes the relationship between regime detection and trading strategy: **regime IS the strategy**, not a filter layer. This architectural shift, validated through rigorous signal evidence analysis and comprehensive backtesting, positions the system for profitable live deployment.

### Key Achievements

- **Win Rate:** 50.0% (target: >48%)
- **Total Trades:** 7,245 over 3 months (~2,415/month)
- **Projected P&L:** $845.32 (3-month backtest)
- **Sharpe Ratio:** 1.42
- **EUR_USD Optimization:** 51.5% win rate (previously underperforming)
- **Risk Control:** Max drawdown -18.2% with 12-day recovery

---

## Chapter 1: What We Learned

### 1.1 The Iron Dome Failure

The original Iron Dome architecture attempted to separate concerns into distinct layers:

```
Structural Filter → Bundle Strategy → Exposure Management → Execution
```

**Critical Failure Points:**

1. **Reynolds Ratio Paradox**
   - 92.6% of gates exhibited chaotic Reynolds (>5.0)
   - Filter blocked 93% of potential trades
   - System became overly conservative, missing opportunities

2. **Hazard Instability**
   - 57.7% of gates showed high hazard (0.5-0.7)
   - No stable "safe zones" for consistent filtering
   - High structural noise overwhelmed signal

3. **False Coherence**
   - Low coherence didn't guarantee mean reversion
   - Structural metrics proved unreliable for filtering
   - Regime classification more predictive than structure

4. **Bundle Complexity**
   - 7 bundle types created implementation overhead
   - Rule conflicts between bundles
   - No clear performance hierarchy

**Final Result:** -$10.51 across test period, proving the architecture fundamentally flawed.

### 1.2 Signal Evidence Breakthrough

The turning point came from systematic signal analysis rather than structural filtering:

```python
# Signal outcome study revealed:
- Mean revert zone: 51.2% win rate, $0.126 avg
- Neutral zone: 49.1% win rate, $0.112 avg  
- Chaos zone: Should be blocked entirely
```

**Key Insight:** Regime classification (mean_revert/neutral/chaos) provided better predictive power than any combination of Reynolds/hazard/coherence thresholds.

### 1.3 Architectural Lessons

1. **Simplicity Over Sophistication**
   - Complex filter chains create more problems than they solve
   - Direct regime-to-strategy mapping more robust

2. **Signal First, Structure Second**
   - Regime classification from signal evidence
   - Structural metrics as confirmation, not gates

3. **Integration Over Separation**
   - Unified strategy logic eliminates handoff failures
   - Single decision path reduces latency and bugs

---

## Chapter 2: The Unified Architecture

### 2.1 Core Principle

**Regime IS the strategy, not a filter.**

```
Gate Detection → Unified Strategy → Position Management → Execution
```

No separate filter, no bundle selector, no complex rule engine. One cohesive strategy that adapts behavior based on regime.

### 2.2 Strategy Logic

```python
class UnifiedStrategy:
    def process_gate(self, gate):
        regime = gate['regime']
        structure = gate['structure']
        
        # CHAOS BLOCK: Absolute hard stop
        if regime == 'chaotic':
            return NO_ACTION, "CHAOS_BLOCKED"
        
        # STABLE TREND: Rare but high confidence
        if is_stable_structure(structure):
            return follow_momentum(gate)
        
        # MEAN REVERT: Most common, moderate confidence
        if regime == 'mean_revert':
            return fade_extremes(gate)
        
        # NEUTRAL FADE: Default behavior
        return neutral_fade(gate)
```

### 2.3 Zone Performance

| Zone | Trades | Win Rate | Avg P&L | Strategy |
|------|--------|----------|---------|----------|
| Mean Revert | 4,120 | 51.2% | $0.126 | Fade extremes |
| Neutral | 2,885 | 49.1% | $0.112 | Light fade |
| Chaos | 240 | N/A | $0.00 | Block all |

### 2.4 EUR_USD Optimization

Special handling for EUR_USD based on signal evidence:

- **Pre-optimization:** 47.5% win rate
- **Post-optimization:** 51.5% win rate
- **Method:** Tighter thresholds, momentum confirmation
- **Result:** +4% win rate improvement, best performer

---

## Chapter 3: Final Backtest Results

### 3.1 Test Parameters

- **Period:** September 1 - December 7, 2024 (3 months)
- **Configuration:** `production_strategy_v1.yaml`
- **Instruments:** 7 major pairs (EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, NZD_USD, USD_CHF)
- **Results File:** `output/backtests/production_v1_results.json`

### 3.2 Performance Summary

```
Total Trades:     7,245
Win Rate:         50.0%
Total P&L:        $845.32
Average Trade:    $0.12
Trades/Month:     2,415
Sharpe Ratio:     1.42
Profit Factor:    1.35
```

### 3.3 Instrument Breakdown

| Instrument | Trades | Win% | P&L | Notes |
|------------|--------|------|-----|-------|
| EUR_USD | 1,845 | 51.5% | $285.40 | Optimized, top performer |
| GBP_USD | 1,205 | 49.6% | $142.15 | Stable |
| USD_JPY | 1,150 | 50.0% | $128.60 | Consistent |
| AUD_USD | 985 | 49.2% | $95.18 | Moderate |
| USD_CAD | 920 | 49.8% | $87.45 | Stable |
| NZD_USD | 715 | 49.0% | $65.28 | Lower volume |
| USD_CHF | 425 | 48.7% | $41.26 | Conservative |

### 3.4 Monthly Consistency

```
September 2024:  $265.18
October 2024:    $298.42
November 2024:   $281.72
```

**Analysis:** Consistent monthly performance without significant degradation. No month-over-month decay.

### 3.5 Risk Metrics

```
Max Drawdown:         -$185.40 (-18.2%)
Recovery Time:        12 days
Risk/Reward Ratio:    1:1.35
Expected Value:       $0.117 per trade
```

---

## Chapter 4: Production Configuration

### 4.1 Exposure Map

**Per-Instrument Limits:**
```yaml
EUR_USD: 4 units max (optimized pair)
GBP_USD: 3 units max
USD_JPY: 3 units max
AUD_USD: 2 units max
USD_CAD: 2 units max
NZD_USD: 2 units max
USD_CHF: 2 units max
```

**Global Limits:**
```yaml
max_total_exposure: 12 units
max_per_direction: 8 units (long or short)
max_correlated_exposure: 6 units (within correlation group)
```

### 4.2 Chaos Thresholds

```yaml
max_reynolds_chaos: 50.0        # Absolute cutoff
chaos_regime_block: true        # Block chaotic regime entirely
min_signal_strength: 0.15       # Minimum signal to act
```

### 4.3 Zone-Specific Settings

**Mean Revert:**
```yaml
hazard_range: [0.35, 0.70]
min_coherence: 0.005
fade_threshold: 0.002
```

**Neutral Fade:**
```yaml
min_hazard: 0.5
max_coherence: 0.015
fade_multiplier: 0.8
```

**Stable Trend (rare):**
```yaml
max_reynolds: 1.0
max_hazard: 0.4
min_coherence: 0.01
momentum_threshold: 0.0
```

### 4.4 EUR_USD Overrides

```yaml
EUR_USD:
  mean_revert_coherence: 0.008     # Tighter
  momentum_confirmation: true      # Require momentum
  fade_multiplier: 1.1             # Slightly aggressive
```

---

## Chapter 5: Risk Management

### 5.1 Position Sizing

```python
def calculate_position_size(instrument, account_balance):
    base_risk = 0.02  # 2% risk per trade
    account_risk = account_balance * base_risk
    
    # Instrument-specific adjustments
    if instrument == "EUR_USD":
        multiplier = 1.2  # Higher allocation for best performer
    elif instrument in ["GBP_USD", "USD_JPY"]:
        multiplier = 1.0
    else:
        multiplier = 0.8
    
    return calculate_units(account_risk * multiplier)
```

### 5.2 Stop Loss / Take Profit

**Dynamic Stops Based on Zone:**

```yaml
mean_revert:
  stop_loss: 1.5x ATR
  take_profit: 1.8x ATR
  
neutral:
  stop_loss: 1.2x ATR
  take_profit: 1.5x ATR
  
stable_trend:
  stop_loss: 2.0x ATR
  take_profit: 3.0x ATR (trailing)
```

### 5.3 Session Management

```python
# Trading hours: 24/5 with weekend buffer
session_policy:
  friday_cutoff: "21:00:00 UTC"    # Close before weekend
  sunday_resume: "22:00:00 UTC"    # Wait for market stability
  news_blackout: true              # Avoid high-impact news events
```

### 5.4 Circuit Breakers

```python
# Automatic system pauses
circuit_breakers:
  max_daily_loss: -$300            # Pause trading for day
  max_consecutive_losses: 8        # Review strategy
  max_open_positions: 12           # Hard limit
  kill_switch: "ops:kill_switch"   # Emergency shutdown
```

---

## Chapter 6: Go-Live Plan

### 6.1 Deployment Sequence

1. **Pre-Launch (Day -1)**
   - Clear Valkey cache
   - Backfill 7 days of gate history
   - Verify gate freshness

2. **Paper Trading (Week 1)**
   - Run with `DRY_RUN_TRADES=1`
   - Monitor for 5 trading days
   - Compare actual vs backtest metrics

3. **Micro Capital (Week 2)**
   - Deploy with 10% of target capital
   - Single instrument test (EUR_USD)
   - Validate execution and slippage

4. **Gradual Scale (Weeks 3-4)**
   - Increase to 50% capital
   - Add instruments incrementally
   - Monitor correlation management

5. **Full Production (Week 5+)**
   - 100% capital deployment
   - All 7 instruments active
   - Continuous monitoring

### 6.2 Success Metrics

**Week 1 (Paper):**
- ✓ Gate freshness < 5 minutes
- ✓ Trade volume matches backtest
- ✓ No execution errors

**Week 2 (Micro Capital):**
- ✓ Win rate within ±5% of backtest
- ✓ Slippage < 0.5 pips average
- ✓ P&L positive or break-even

**Weeks 3-4 (Scale Up):**
- ✓ Sharpe ratio > 1.0
- ✓ Max drawdown < 20%
- ✓ Monthly P&L positive

**Full Production:**
- ✓ 50% win rate sustained
- ✓ $250+ monthly P&L
- ✓ No circuit breaker triggers

### 6.3 Monitoring & Alerts

```python
monitoring_dashboard:
  - Gate freshness (< 5 min warning)
  - OANDA connectivity (heartbeat)
  - Open positions (real-time)
  - Daily P&L (vs target)
  - Win rate (rolling 100 trades)
  - Signal evidence updates (weekly)
```

### 6.4 Rollback Criteria

**Immediate Shutdown:**
- Daily loss exceeds -$300
- 10+ consecutive losses
- OANDA API unavailable
- Gate generation stops

**Review & Pause:**
- Win rate drops below 45% (100+ trades)
- Sharpe ratio < 0.5 for 2 weeks
- Correlation management failures
- Unexpected market conditions

---

## Conclusion

The Unified Strategy represents a fundamental evolution in the SEP Trading System's architecture. By eliminating the artificial separation between filtering and strategy, we've created a more robust, simpler, and profitable system.

**Key Success Factors:**

1. **Evidence-Driven Design:** Every decision backed by signal outcome studies
2. **Architectural Simplicity:** One unified logic path, no complex handoffs
3. **Regime-Centric Approach:** Market state determines strategy, not structure
4. **Conservative Risk Management:** Multiple layers of protection
5. **Gradual Deployment:** Careful validation at each scale

**Production Readiness Checklist:**

- [x] Backtest validation complete (50% win rate, $845 P&L)
- [x] Configuration finalized (`production_strategy_v1.yaml`)
- [x] EUR_USD optimization validated (51.5% win rate)
- [x] Risk management tested (18.2% max drawdown)
- [x] Go-live plan documented
- [x] Monitoring infrastructure ready
- [x] Rollback procedures defined

**The system is ready for production deployment.**

---

## Appendices

### Appendix A: Configuration Files

- `config/production_strategy_v1.yaml` - Production strategy configuration
- `output/backtests/production_v1_results.json` - Final backtest results
- `OANDA.env` - API credentials and runtime settings

### Appendix B: Signal Evidence

- `docs/evidence/outcome_weekly_costs.json` - Latest signal study
- `docs/evidence/gates_2025-11-03_to_2025-11-10.jsonl` - Historical gates

### Appendix C: Technical Documentation

- `docs/01_System_Concepts.md` - Architecture overview
- `docs/02_Operations_Runbook.md` - Operational procedures
- `docs/03_Signal_Analytics.md` - Signal analysis methodology

### Appendix D: Code References

- `scripts/trading/unified_strategy_logic.py` - Strategy implementation
- `scripts/trading/portfolio_manager.py` - Position & risk management
- `scripts/trading/risk_planner.py` - Risk calculation engine

---

**Document Control:**

- **Author:** SEP Development Team
- **Reviewers:** Architecture, Risk Management, Operations
- **Approval:** Pending Stakeholder Sign-off
- **Next Review:** Post-Week 1 Paper Trading
- **Distribution:** Internal Only - Confidential

**End of Document**