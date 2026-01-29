# 🎯 SB-ALGO 3-Tier System - Final Configuration

**Backtest:** Dec 1, 2025 - Jan 25, 2026 (52 game days)  
**Status:** ✅ LIVE  
**Last Updated:** Jan 29, 2026

---

## 📊 Performance Summary

| Tier | Record | Win % | PPD | Units |
|------|--------|-------|-----|-------|
| 🏆 T1 Elite | 36-8 | **81.8%** | 0.85 | 1.5u |
| ✅ T2 Strong | 60-23 | **72.3%** | 1.60 | 1.0u |
| 📊 T3 Volume | 75-33 | **69.4%** | 2.08 | 0.5u |
| **TOTAL** | **171-64** | **72.8%** | **4.53** | |

**ROI:** +41.8% | **Target:** 4+ PPD ✅

---

## 🔬 Math Engines Used

1. **PlayerPropEngine** - Stat-specific distributions (Gaussian/Poisson)
2. **KellyEngine** - Fractional Kelly sizing (conservative profile)
3. **InjuryEngine** - Team injury impact analysis

---

## 🏆 T1 ELITE FILTERS (1.5 units)

High confidence picks with strict thresholds.

| Stat | Record | Win % | Edge | CV | Projection |
|------|--------|-------|------|-----|------------|
| PTS UNDER | 16-4 | 80.0% | ≥15% | ≤0.40 | ≥20 pts |
| REB OVER | 4-1 | 80.0% | ≥25% | ≤0.30 | ≥10 reb |
| REB UNDER | 10-2 | 83.3% | ≥20% | ≤0.35 | ≥4 reb |
| AST UNDER | 6-1 | 85.7% | ≥15% | ≤0.35 | ≥6 ast |

---

## ✅ T2 STRONG FILTERS (1.0 units)

Solid picks with balanced risk/reward.

| Stat | Record | Win % | Edge | CV | Projection |
|------|--------|-------|------|-----|------------|
| PTS UNDER | 11-3 | 78.6% | ≥15% | ≤0.35 | ≥20 pts |
| REB UNDER | 17-7 | 70.8% | ≥20% | ≤0.45 | ≥6 reb |
| AST OVER | 19-8 | 70.4% | ≥30% | ≤0.30 | ≥3 ast |
| AST UNDER | 13-5 | 72.2% | ≥10% | ≤0.35 | ≥6 ast |

---

## 📊 T3 VOLUME FILTERS (0.5 units)

Volume plays with managed risk sizing.

| Stat | Record | Win % | Edge | CV | Projection |
|------|--------|-------|------|-----|------------|
| PTS UNDER | 35-16 | 68.6% | ≥10% | ≤0.40 | ≥20 pts |
| REB UNDER | 20-8 | 71.4% | ≥20% | ≤0.45 | ≥5 reb |
| AST UNDER | 20-9 | 69.0% | ≥10% | ≤0.45 | ≥6 ast |

---

## 🚫 Excluded Filters (Under 68%)

| Stat | Best Win % | Reason |
|------|------------|--------|
| PTS OVER | 65.2% | Volume dilutes accuracy |
| REB OVER | 64.5% | Too volatile |
| AST OVER | 59.4% | Too unpredictable |

---

## 💰 Daily Expectation

| Metric | Value |
|--------|-------|
| **Min picks** | 2-3 (slow days) |
| **Avg picks** | 4-5 per day |
| **Max picks** | 8-10 (heavy slates) |
| **Daily risk** | ~4.5 units |
| **Expected win rate** | 72-73% |

---

## 📈 Recent Results

| Date | Record | P/L |
|------|--------|-----|
| Jan 28, 2026 | 3-0 | +4.5u |
| Jan 27, 2026 | TBD | TBD |
| Jan 26, 2026 | TBD | TBD |

---

## ⚙️ Technical Details

**Edge Calculation:**
```
edge = (projection - line) / line × 100
```

**Projection Formula (L5/10/15 weighted):**
```
proj = 0.40×L5 + 0.30×L10 + 0.20×L15 + 0.10×Season
```

**CV (Coefficient of Variation):**
```
cv = std_dev / mean
```
Lower CV = more consistent player = safer bet.

---

## ✅ Verification

- [x] T1 filters enabled and tested
- [x] T2 filters enabled and tested  
- [x] T3 filters enabled and tested (FIXED Jan 29)
- [x] Unit sizes correct (T1=1.5u, T2=1.0u, T3=0.5u)
- [x] Pushed to production

---

**Built by SB-ALGO Team | v4.0**
