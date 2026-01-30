#!/usr/bin/env python3
"""
================================================================================
CALIBRATION ENGINE v3.0 - CRITICAL
================================================================================
Makes your probability estimates ACCURATE.

WHY THIS IS CRITICAL:
---------------------
Without calibration:
- "Model says 65%" might actually be 58% historically
- Kelly betting on uncalibrated probabilities = SUICIDE
- You'll overbet edges that don't exist

With calibration:
- "Model says 65%" is actually 65% (or we know the correction)
- Kelly betting is mathematically optimal
- You know your actual edge

WHAT IS CALIBRATION?
--------------------
If you predict 60% win probability:
- Perfect calibration: You win exactly 60% of those bets
- Overconfident: You win less than 60%
- Underconfident: You win more than 60%

METHODS:
--------
1. Platt Scaling: Logistic regression on raw probabilities
2. Isotonic Regression: Non-parametric, monotonic transformation
3. Temperature Scaling: Simple division by temperature parameter
4. Histogram Binning: Group into bins, use empirical win rate

RELIABILITY METRICS:
--------------------
- Expected Calibration Error (ECE): Average deviation from perfect
- Maximum Calibration Error (MCE): Worst case deviation
- Brier Score: Squared error of probabilities
- Log Loss: Information-theoretic measure

================================================================================
"""

import numpy as np
from scipy import stats
from scipy.optimize import minimize
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Simple isotonic regression implementation (no sklearn needed)
def simple_isotonic_regression(x, y):
    """Simple implementation of isotonic regression using PAVA algorithm"""
    n = len(x)
    if n == 0:
        return lambda v: v
    
    # Sort by x
    order = np.argsort(x)
    x_sorted = np.array(x)[order]
    y_sorted = np.array(y)[order]
    
    # Pool Adjacent Violators Algorithm (PAVA)
    y_iso = np.copy(y_sorted).astype(float)
    
    i = 0
    while i < n - 1:
        if y_iso[i] > y_iso[i + 1]:
            # Pool
            j = i + 1
            while j < n and y_iso[i] > y_iso[j]:
                j += 1
            # Average
            avg = np.mean(y_iso[i:j])
            y_iso[i:j] = avg
            i = max(0, i - 1)
        else:
            i += 1
    
    # Return interpolation function
    def predict(values):
        values = np.atleast_1d(values)
        result = np.interp(values, x_sorted, y_iso)
        return result if len(result) > 1 else result[0]
    
    return predict


class CalibrationEngine:
    """
    ============================================================================
    CALIBRATION ENGINE
    ============================================================================
    
    Ensures probability estimates are reliable and accurate.
    
    Primary Functions:
    1. Calibrate raw model probabilities
    2. Track calibration by market type
    3. Calculate reliability metrics
    4. Adjust confidence for Kelly betting
    
    ============================================================================
    """
    
    def __init__(self):
        """Initialize calibration engine"""
        # Calibration parameters (learned from historical data)
        self.platt_params = {}  # {market_type: (A, B)}
        self.isotonic_models = {}  # {market_type: IsotonicRegression}
        self.temperature = {}  # {market_type: T}
        
        # Historical tracking
        self.calibration_history = {
            'spread': [],
            'total': [],
            'moneyline': [],
            'player_prop': [],
            'xgboost': [],  # v4.1: XGBoost gatekeeper predictions
        }
        
        # Default calibration adjustments (prior to learning)
        self._default_adjustments = {
            'spread': {'slope': 0.92, 'intercept': 0.04},
            'total': {'slope': 0.90, 'intercept': 0.05},
            'moneyline': {'slope': 0.95, 'intercept': 0.025},
            'player_prop': {'slope': 0.85, 'intercept': 0.075},
            'xgboost': {'slope': 0.95, 'intercept': 0.02},  # XGBoost predictions
        }
    
    # ==========================================================================
    # CALIBRATION METHODS
    # ==========================================================================
    
    def calibrate_probability(self, raw_prob: float, market_type: str = 'spread',
                              method: str = 'default') -> Dict:
        """
        Calibrate a raw probability estimate.
        
        Args:
            raw_prob: Raw model probability (0 to 1)
            market_type: Type of bet (spread, total, moneyline, player_prop)
            method: Calibration method (default, platt, isotonic, temperature)
            
        Returns:
            Calibrated probability with metadata
        """
        if raw_prob <= 0 or raw_prob >= 1:
            return {
                'raw_probability': raw_prob,
                'calibrated_probability': max(0.01, min(0.99, raw_prob)),
                'method': 'clamped',
                'adjustment': 0,
            }
        
        if method == 'platt' and market_type in self.platt_params:
            calibrated = self._platt_scale(raw_prob, market_type)
        elif method == 'isotonic' and market_type in self.isotonic_models:
            calibrated = self._isotonic_scale(raw_prob, market_type)
        elif method == 'temperature' and market_type in self.temperature:
            calibrated = self._temperature_scale(raw_prob, market_type)
        else:
            # Use default linear adjustment
            calibrated = self._default_calibration(raw_prob, market_type)
        
        # Clamp to valid probability range
        calibrated = max(0.01, min(0.99, calibrated))
        
        adjustment = calibrated - raw_prob
        
        return {
            'raw_probability': round(raw_prob, 4),
            'calibrated_probability': round(calibrated, 4),
            'method': method,
            'market_type': market_type,
            'adjustment': round(adjustment, 4),
            'adjustment_pct': round(adjustment * 100, 2),
            'confidence_impact': self._assess_confidence_impact(adjustment),
        }
    
    def _default_calibration(self, prob: float, market_type: str) -> float:
        """
        Apply default linear calibration.
        
        Most models are OVERCONFIDENT - they predict 65% when reality is 60%.
        This shrinks predictions toward 50%.
        
        Formula: calibrated = slope * (raw - 0.5) + 0.5 + intercept_adjustment
        """
        params = self._default_adjustments.get(market_type, {'slope': 0.90, 'intercept': 0.05})
        
        slope = params['slope']
        intercept = params['intercept']
        
        # Shrink toward 50%
        deviation = prob - 0.5
        calibrated = 0.5 + (deviation * slope)
        
        # Small boost for favorites (they tend to cover more than expected)
        if prob > 0.5:
            calibrated += intercept * (prob - 0.5) * 2
        else:
            calibrated -= intercept * (0.5 - prob) * 2
        
        return calibrated
    
    def _platt_scale(self, prob: float, market_type: str) -> float:
        """
        Platt scaling: logistic regression on log-odds.
        
        P_calibrated = 1 / (1 + exp(A * logit(P_raw) + B))
        """
        A, B = self.platt_params[market_type]
        
        # Convert to log-odds
        logit = np.log(prob / (1 - prob))
        
        # Apply scaling
        scaled_logit = A * logit + B
        
        # Convert back to probability
        calibrated = 1 / (1 + np.exp(-scaled_logit))
        
        return calibrated
    
    def _isotonic_scale(self, prob: float, market_type: str) -> float:
        """
        Isotonic regression: non-parametric monotonic calibration.
        """
        ir_func = self.isotonic_models[market_type]
        calibrated = ir_func(prob)
        return float(calibrated)
    
    def _temperature_scale(self, prob: float, market_type: str) -> float:
        """
        Temperature scaling: divide logits by temperature.
        
        T > 1: Softens probabilities (toward 50%)
        T < 1: Sharpens probabilities (away from 50%)
        """
        T = self.temperature[market_type]
        
        # Convert to log-odds
        logit = np.log(prob / (1 - prob))
        
        # Apply temperature
        scaled_logit = logit / T
        
        # Convert back
        calibrated = 1 / (1 + np.exp(-scaled_logit))
        
        return calibrated
    
    def _assess_confidence_impact(self, adjustment: float) -> str:
        """Assess what the calibration adjustment means"""
        if abs(adjustment) < 0.01:
            return "MINIMAL - Model well-calibrated"
        elif adjustment < -0.03:
            return "SIGNIFICANT_DOWN - Model was overconfident"
        elif adjustment > 0.03:
            return "SIGNIFICANT_UP - Model was underconfident"
        elif adjustment < 0:
            return "SLIGHT_DOWN - Minor overconfidence"
        else:
            return "SLIGHT_UP - Minor underconfidence"
    
    # ==========================================================================
    # LEARNING CALIBRATION PARAMETERS
    # ==========================================================================
    
    def fit_platt_scaling(self, predictions: List[float], outcomes: List[int],
                          market_type: str) -> Dict:
        """
        Learn Platt scaling parameters from historical data.
        
        Args:
            predictions: List of raw predicted probabilities
            outcomes: List of actual outcomes (1=win, 0=loss)
            market_type: Market type to calibrate
            
        Returns:
            Fitted parameters and diagnostics
        """
        if len(predictions) < 50:
            return {'error': 'Need at least 50 samples for Platt scaling'}
        
        predictions = np.array(predictions)
        outcomes = np.array(outcomes)
        
        # Convert to log-odds
        logits = np.log(predictions / (1 - predictions + 1e-10))
        
        # Fit logistic regression
        def neg_log_likelihood(params):
            A, B = params
            scaled = A * logits + B
            probs = 1 / (1 + np.exp(-scaled))
            probs = np.clip(probs, 1e-10, 1 - 1e-10)
            return -np.sum(outcomes * np.log(probs) + (1 - outcomes) * np.log(1 - probs))
        
        result = minimize(neg_log_likelihood, [1.0, 0.0], method='L-BFGS-B')
        A, B = result.x
        
        self.platt_params[market_type] = (A, B)
        
        # Calculate calibration metrics
        calibrated = 1 / (1 + np.exp(-(A * logits + B)))
        ece = self._calculate_ece(calibrated, outcomes)
        brier = np.mean((calibrated - outcomes) ** 2)
        
        return {
            'market_type': market_type,
            'A': round(A, 4),
            'B': round(B, 4),
            'samples': len(predictions),
            'ece_before': round(self._calculate_ece(predictions, outcomes), 4),
            'ece_after': round(ece, 4),
            'brier_score': round(brier, 4),
            'interpretation': f"Calibration improved ECE from {self._calculate_ece(predictions, outcomes):.1%} to {ece:.1%}"
        }
    
    def fit_isotonic_regression(self, predictions: List[float], outcomes: List[int],
                                 market_type: str) -> Dict:
        """
        Learn isotonic regression calibration.
        
        Non-parametric, ensures monotonicity (higher pred = higher actual).
        """
        if len(predictions) < 100:
            return {'error': 'Need at least 100 samples for isotonic regression'}
        
        predictions = np.array(predictions)
        outcomes = np.array(outcomes)
        
        # Fit simple isotonic regression (no sklearn needed)
        ir_func = simple_isotonic_regression(predictions, outcomes)
        
        self.isotonic_models[market_type] = ir_func
        
        # Calculate metrics
        calibrated = np.array([ir_func(p) for p in predictions])
        ece = self._calculate_ece(calibrated, outcomes)
        
        return {
            'market_type': market_type,
            'samples': len(predictions),
            'ece_before': round(self._calculate_ece(predictions, outcomes), 4),
            'ece_after': round(ece, 4),
            'method': 'isotonic_regression',
        }
    
    def fit_temperature_scaling(self, predictions: List[float], outcomes: List[int],
                                 market_type: str) -> Dict:
        """
        Learn optimal temperature for scaling.
        """
        if len(predictions) < 50:
            return {'error': 'Need at least 50 samples'}
        
        predictions = np.array(predictions)
        outcomes = np.array(outcomes)
        
        logits = np.log(predictions / (1 - predictions + 1e-10))
        
        def neg_log_likelihood(T):
            scaled = logits / T[0]
            probs = 1 / (1 + np.exp(-scaled))
            probs = np.clip(probs, 1e-10, 1 - 1e-10)
            return -np.sum(outcomes * np.log(probs) + (1 - outcomes) * np.log(1 - probs))
        
        result = minimize(neg_log_likelihood, [1.0], bounds=[(0.1, 10.0)])
        T = result.x[0]
        
        self.temperature[market_type] = T
        
        return {
            'market_type': market_type,
            'temperature': round(T, 4),
            'interpretation': 'T > 1 means model was overconfident' if T > 1 else 'T < 1 means model was underconfident',
            'samples': len(predictions),
        }
    
    # ==========================================================================
    # CALIBRATION METRICS
    # ==========================================================================
    
    def _calculate_ece(self, predictions: np.ndarray, outcomes: np.ndarray,
                       n_bins: int = 10) -> float:
        """
        Calculate Expected Calibration Error (ECE).
        
        ECE = Σ (|bin| / n) * |accuracy(bin) - confidence(bin)|
        
        Lower is better. 0 = perfect calibration.
        """
        bin_edges = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        
        for i in range(n_bins):
            mask = (predictions >= bin_edges[i]) & (predictions < bin_edges[i + 1])
            if np.sum(mask) > 0:
                bin_accuracy = np.mean(outcomes[mask])
                bin_confidence = np.mean(predictions[mask])
                bin_size = np.sum(mask) / len(predictions)
                ece += bin_size * abs(bin_accuracy - bin_confidence)
        
        return ece
    
    def calculate_calibration_metrics(self, predictions: List[float],
                                       outcomes: List[int]) -> Dict:
        """
        Calculate comprehensive calibration metrics.
        
        Args:
            predictions: Predicted probabilities
            outcomes: Actual outcomes (1=win, 0=loss)
            
        Returns:
            Full calibration analysis
        """
        predictions = np.array(predictions)
        outcomes = np.array(outcomes)
        
        # ECE
        ece = self._calculate_ece(predictions, outcomes)
        
        # MCE (Maximum Calibration Error)
        bin_edges = np.linspace(0, 1, 11)
        max_error = 0
        for i in range(10):
            mask = (predictions >= bin_edges[i]) & (predictions < bin_edges[i + 1])
            if np.sum(mask) > 5:  # Need enough samples
                bin_accuracy = np.mean(outcomes[mask])
                bin_confidence = np.mean(predictions[mask])
                max_error = max(max_error, abs(bin_accuracy - bin_confidence))
        
        # Brier Score
        brier = np.mean((predictions - outcomes) ** 2)
        
        # Log Loss
        eps = 1e-10
        log_loss = -np.mean(outcomes * np.log(predictions + eps) + 
                          (1 - outcomes) * np.log(1 - predictions + eps))
        
        # Calibration curve data
        calibration_curve = []
        for i in range(10):
            low = i / 10
            high = (i + 1) / 10
            mask = (predictions >= low) & (predictions < high)
            if np.sum(mask) > 0:
                calibration_curve.append({
                    'bin': f'{low:.0%}-{high:.0%}',
                    'predicted': round(np.mean(predictions[mask]), 3),
                    'actual': round(np.mean(outcomes[mask]), 3),
                    'count': int(np.sum(mask)),
                })
        
        # Overall assessment
        if ece < 0.03:
            assessment = 'EXCELLENT - Model is well-calibrated'
        elif ece < 0.06:
            assessment = 'GOOD - Minor calibration issues'
        elif ece < 0.10:
            assessment = 'FAIR - Moderate calibration needed'
        else:
            assessment = 'POOR - Significant miscalibration'
        
        return {
            'samples': len(predictions),
            'win_rate': round(np.mean(outcomes), 4),
            'avg_predicted': round(np.mean(predictions), 4),
            
            # Core metrics
            'ece': round(ece, 4),
            'mce': round(max_error, 4),
            'brier_score': round(brier, 4),
            'log_loss': round(log_loss, 4),
            
            # Assessment
            'assessment': assessment,
            'calibration_curve': calibration_curve,
            
            # Interpretation
            'overconfident': np.mean(predictions) > np.mean(outcomes),
            'confidence_gap': round(np.mean(predictions) - np.mean(outcomes), 4),
        }
    
    # ==========================================================================
    # RELIABILITY BY SEGMENT
    # ==========================================================================
    
    def analyze_by_probability_band(self, predictions: List[float],
                                     outcomes: List[int]) -> Dict:
        """
        Analyze calibration by probability band.
        
        Shows where model is most/least accurate.
        """
        predictions = np.array(predictions)
        outcomes = np.array(outcomes)
        
        bands = [
            (0.50, 0.55, 'Toss-up'),
            (0.55, 0.60, 'Slight edge'),
            (0.60, 0.65, 'Moderate edge'),
            (0.65, 0.70, 'Strong edge'),
            (0.70, 0.80, 'Very strong'),
            (0.80, 1.00, 'Lock'),
        ]
        
        analysis = []
        for low, high, name in bands:
            mask = (predictions >= low) & (predictions < high)
            if np.sum(mask) >= 10:
                predicted = np.mean(predictions[mask])
                actual = np.mean(outcomes[mask])
                gap = actual - predicted
                
                analysis.append({
                    'band': name,
                    'range': f'{low:.0%}-{high:.0%}',
                    'count': int(np.sum(mask)),
                    'predicted_win_rate': round(predicted, 3),
                    'actual_win_rate': round(actual, 3),
                    'gap': round(gap, 3),
                    'reliable': abs(gap) < 0.05,
                })
        
        return {
            'bands': analysis,
            'most_reliable': max(analysis, key=lambda x: -abs(x['gap']))['band'] if analysis else None,
            'least_reliable': max(analysis, key=lambda x: abs(x['gap']))['band'] if analysis else None,
        }
    
    def analyze_by_spread_band(self, spreads: List[float], predictions: List[float],
                                outcomes: List[int]) -> Dict:
        """
        Analyze calibration by spread size.
        
        Model might be better at big spreads vs close games.
        """
        spreads = np.array(spreads)
        predictions = np.array(predictions)
        outcomes = np.array(outcomes)
        
        bands = [
            (0, 3, 'Close (0-3)'),
            (3, 6, 'Small (3-6)'),
            (6, 10, 'Medium (6-10)'),
            (10, 20, 'Large (10+)'),
        ]
        
        analysis = []
        for low, high, name in bands:
            mask = (np.abs(spreads) >= low) & (np.abs(spreads) < high)
            if np.sum(mask) >= 10:
                ece = self._calculate_ece(predictions[mask], outcomes[mask])
                accuracy = np.mean(outcomes[mask])
                
                analysis.append({
                    'spread_band': name,
                    'count': int(np.sum(mask)),
                    'ece': round(ece, 4),
                    'accuracy': round(accuracy, 3),
                    'reliable': ece < 0.06,
                })
        
        return {'by_spread': analysis}
    
    # ==========================================================================
    # KELLY CONFIDENCE ADJUSTMENT
    # ==========================================================================
    
    def adjust_for_kelly(self, raw_prob: float, market_type: str,
                         model_confidence: float = 100) -> Dict:
        """
        Adjust probability for safe Kelly betting.
        
        Combines:
        1. Calibration adjustment
        2. Model confidence penalty
        3. Conservative shrinkage
        
        Args:
            raw_prob: Raw model probability
            market_type: Market type
            model_confidence: Model's self-reported confidence (0-100)
            
        Returns:
            Kelly-safe probability
        """
        # Step 1: Calibrate
        calibrated = self.calibrate_probability(raw_prob, market_type)
        cal_prob = calibrated['calibrated_probability']
        
        # Step 2: Apply confidence penalty
        # Low confidence = shrink toward 50%
        confidence_factor = model_confidence / 100
        confidence_adjusted = 0.5 + (cal_prob - 0.5) * confidence_factor
        
        # Step 3: Conservative shrinkage for Kelly
        # Kelly is very sensitive to probability errors
        # Shrink by additional 5-10% toward 50%
        kelly_shrinkage = 0.92  # 8% shrinkage
        kelly_safe = 0.5 + (confidence_adjusted - 0.5) * kelly_shrinkage
        
        # Calculate Kelly-relevant metrics
        edge_raw = raw_prob - 0.5
        edge_kelly = kelly_safe - 0.5
        edge_reduction = 1 - (edge_kelly / edge_raw) if edge_raw != 0 else 0
        
        return {
            'raw_probability': round(raw_prob, 4),
            'calibrated_probability': round(cal_prob, 4),
            'confidence_adjusted': round(confidence_adjusted, 4),
            'kelly_safe_probability': round(kelly_safe, 4),
            
            'raw_edge': round(edge_raw, 4),
            'kelly_edge': round(edge_kelly, 4),
            'edge_reduction_pct': round(edge_reduction * 100, 1),
            
            'model_confidence': model_confidence,
            'kelly_shrinkage': kelly_shrinkage,
            
            'recommendation': self._kelly_recommendation(kelly_safe, raw_prob),
        }
    
    def _kelly_recommendation(self, kelly_prob: float, raw_prob: float) -> str:
        """Generate Kelly betting recommendation"""
        if kelly_prob < 0.52:
            return "NO_BET - Insufficient edge after calibration"
        elif kelly_prob < 0.55:
            return "SMALL_BET - Marginal edge, use quarter Kelly"
        elif kelly_prob < 0.60:
            return "STANDARD_BET - Solid edge, use half Kelly"
        elif kelly_prob < 0.65:
            return "GOOD_BET - Strong edge, can use 2/3 Kelly"
        else:
            return "STRONG_BET - High confidence, can use full Kelly fraction"
    
    # ==========================================================================
    # TRACKING AND MONITORING
    # ==========================================================================
    
    def add_result(self, market_type: str, predicted: float, outcome: int,
                   metadata: Dict = None):
        """
        Add a bet result for tracking calibration over time.
        
        Args:
            market_type: Type of bet
            predicted: Predicted probability
            outcome: Actual outcome (1=win, 0=loss)
            metadata: Additional info (spread, total, etc.)
        """
        record = {
            'predicted': predicted,
            'outcome': outcome,
            'timestamp': np.datetime64('now'),
            'metadata': metadata or {},
        }
        
        if market_type in self.calibration_history:
            self.calibration_history[market_type].append(record)
    
    def get_recent_calibration(self, market_type: str, n_bets: int = 100) -> Dict:
        """
        Get calibration metrics for recent bets.
        
        Args:
            market_type: Market type to analyze
            n_bets: Number of recent bets to analyze
            
        Returns:
            Recent calibration metrics
        """
        history = self.calibration_history.get(market_type, [])
        
        if len(history) < 20:
            return {'error': f'Only {len(history)} bets tracked, need at least 20'}
        
        recent = history[-n_bets:]
        predictions = [r['predicted'] for r in recent]
        outcomes = [r['outcome'] for r in recent]
        
        metrics = self.calculate_calibration_metrics(predictions, outcomes)
        metrics['period'] = f'Last {len(recent)} bets'
        metrics['market_type'] = market_type
        
        return metrics


# ==============================================================================
# TEST SUITE
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("CALIBRATION ENGINE v3.0 - TEST SUITE")
    print("=" * 80)
    
    engine = CalibrationEngine()
    
    # -------------------------------------------------------------------------
    # Test 1: Basic calibration
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 1: BASIC CALIBRATION")
    print("=" * 80)
    
    test_probs = [0.55, 0.60, 0.65, 0.70, 0.75]
    
    print("\n  Default calibration adjustments:")
    for prob in test_probs:
        cal = engine.calibrate_probability(prob, 'spread')
        print(f"    {prob:.0%} → {cal['calibrated_probability']:.1%} ({cal['adjustment_pct']:+.1f}%)")
    
    # -------------------------------------------------------------------------
    # Test 2: Different market types
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 2: CALIBRATION BY MARKET TYPE")
    print("=" * 80)
    
    prob = 0.65
    for market in ['spread', 'total', 'moneyline', 'player_prop']:
        cal = engine.calibrate_probability(prob, market)
        print(f"\n  {market.upper()}: {prob:.0%} → {cal['calibrated_probability']:.1%}")
        print(f"    {cal['confidence_impact']}")
    
    # -------------------------------------------------------------------------
    # Test 3: Simulate historical data and fit
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 3: FIT CALIBRATION FROM DATA")
    print("=" * 80)
    
    # Simulate overconfident model
    np.random.seed(42)
    n_samples = 200
    
    # Raw predictions (overconfident)
    raw_preds = np.random.beta(3, 2, n_samples)  # Skewed toward high probs
    raw_preds = np.clip(raw_preds, 0.05, 0.95)
    
    # Actual outcomes (less favorable than predicted)
    outcomes = (np.random.random(n_samples) < (raw_preds * 0.9)).astype(int)
    
    print(f"\n  Simulated {n_samples} bets (overconfident model)")
    print(f"  Avg Predicted: {np.mean(raw_preds):.1%}")
    print(f"  Actual Win Rate: {np.mean(outcomes):.1%}")
    
    # Calculate metrics before
    metrics_before = engine.calculate_calibration_metrics(list(raw_preds), list(outcomes))
    print(f"\n  Before Calibration:")
    print(f"    ECE: {metrics_before['ece']:.4f}")
    print(f"    Brier: {metrics_before['brier_score']:.4f}")
    print(f"    Assessment: {metrics_before['assessment']}")
    
    # Fit Platt scaling
    fit_result = engine.fit_platt_scaling(list(raw_preds), list(outcomes), 'spread')
    print(f"\n  After Platt Scaling:")
    print(f"    A={fit_result['A']:.3f}, B={fit_result['B']:.3f}")
    print(f"    ECE: {fit_result['ece_after']:.4f}")
    print(f"    {fit_result['interpretation']}")
    
    # -------------------------------------------------------------------------
    # Test 4: Calibration metrics
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 4: CALIBRATION METRICS")
    print("=" * 80)
    
    print("\n  Full calibration analysis:")
    print(f"    Samples: {metrics_before['samples']}")
    print(f"    ECE: {metrics_before['ece']:.4f} (lower is better)")
    print(f"    MCE: {metrics_before['mce']:.4f} (worst bin)")
    print(f"    Brier: {metrics_before['brier_score']:.4f}")
    print(f"    Log Loss: {metrics_before['log_loss']:.4f}")
    print(f"    Overconfident: {metrics_before['overconfident']}")
    
    print("\n  Calibration curve:")
    for bin_data in metrics_before['calibration_curve']:
        diff = bin_data['actual'] - bin_data['predicted']
        marker = '✓' if abs(diff) < 0.05 else '✗'
        print(f"    {bin_data['bin']}: Pred {bin_data['predicted']:.0%} vs Actual {bin_data['actual']:.0%} {marker}")
    
    # -------------------------------------------------------------------------
    # Test 5: Kelly adjustment
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 5: KELLY BETTING ADJUSTMENT")
    print("=" * 80)
    
    test_cases = [
        (0.55, 100, 'spread'),
        (0.60, 100, 'spread'),
        (0.65, 80, 'spread'),
        (0.70, 60, 'player_prop'),
    ]
    
    for prob, conf, market in test_cases:
        kelly = engine.adjust_for_kelly(prob, market, conf)
        print(f"\n  Raw: {prob:.0%}, Confidence: {conf}%, Market: {market}")
        print(f"    Calibrated: {kelly['calibrated_probability']:.1%}")
        print(f"    Kelly-Safe: {kelly['kelly_safe_probability']:.1%}")
        print(f"    Edge Reduction: {kelly['edge_reduction_pct']:.0f}%")
        print(f"    💡 {kelly['recommendation']}")
    
    # -------------------------------------------------------------------------
    # Test 6: Analysis by probability band
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 6: ANALYSIS BY PROBABILITY BAND")
    print("=" * 80)
    
    band_analysis = engine.analyze_by_probability_band(list(raw_preds), list(outcomes))
    
    print("\n  Reliability by prediction confidence:")
    for band in band_analysis['bands']:
        reliable = '✓' if band['reliable'] else '✗'
        print(f"    {band['band']} ({band['range']}): Pred {band['predicted_win_rate']:.0%} vs Actual {band['actual_win_rate']:.0%} {reliable}")
    
    print(f"\n  Most reliable: {band_analysis['most_reliable']}")
    print(f"  Least reliable: {band_analysis['least_reliable']}")
    
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("✅ CALIBRATION ENGINE v3.0 - ALL TESTS COMPLETE")
    print("=" * 80)
