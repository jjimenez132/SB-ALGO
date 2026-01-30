#!/usr/bin/env python3
"""
================================================================================
XGBOOST GATEKEEPER v1.0 - Final Pick Approval
================================================================================
Machine learning classifier to approve/reject picks based on historical patterns.

Focus on PRECISION over RECALL - we want to kill bad picks, not find new ones.

Features used:
- poisson_prob: Hit probability from Poisson model
- edge_pct: Edge vs book line (%)
- cv: Coefficient of variation (consistency)
- market_odds: Current market odds
- gp: Games played
- mpg: Minutes per game
- hit_rate: Historical hit rate vs similar lines
- stat_type: PTS/REB/AST (encoded)
- is_over: OVER=1, UNDER=0
- opp_def_factor: Opponent defense rating

Label: Win=1, Loss=0
================================================================================
"""

import numpy as np
import pickle
import os
from typing import Dict, Optional, List
from datetime import datetime

# XGBoost import with fallback
try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("⚠️ XGBoost not installed. Run: pip install xgboost")

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'xgboost_gatekeeper_v2.pkl')


class XGBoostGatekeeper:
    """
    XGBoost-based final gatekeeper for prop picks.
    
    Purpose: Kill underperforming picks (especially T3) that pass filter thresholds
    but have poor feature combinations that historically lose.
    """
    
    def __init__(self):
        self.model = None
        self.is_loaded = False
        self.feature_names = [
            'poisson_prob', 'edge_pct', 'cv', 'market_prob',
            'gp', 'mpg', 'hit_rate', 'is_over', 'stat_pts', 'stat_reb', 'stat_ast'
        ]
        
        # Tier-specific approval thresholds (tuned via backtest)
        # Rule: Only kill picks where killed WR < 50% (more losers than winners)
        self.thresholds = {
            1: 0.40,  # T1: Already elite, minimal gating
            2: 0.52,  # T2: Kill picks with < 48.8% WR
            3: 0.50,  # T3: Kill picks with < 47.6% WR
        }
        
        # Try to load existing model
        self._load_model()
    
    def _load_model(self):
        """Load pre-trained model if available"""
        if not XGBOOST_AVAILABLE:
            return
            
        if os.path.exists(MODEL_PATH):
            try:
                with open(MODEL_PATH, 'rb') as f:
                    data = pickle.load(f)
                # v2 format: dict with 'model' and 'feature_names'
                if isinstance(data, dict) and 'model' in data:
                    self.model = data['model']
                    self.feature_names = data.get('feature_names', self.feature_names)
                else:
                    self.model = data  # v1 format: just the model
                self.is_loaded = True
                print(f"   ✅ XGBoost gatekeeper v2 loaded")
            except Exception as e:
                print(f"   ⚠️ Could not load XGBoost model: {e}")
    
    def _save_model(self):
        """Save trained model"""
        if self.model:
            with open(MODEL_PATH, 'wb') as f:
                pickle.dump(self.model, f)
            print(f"   ✅ Model saved to {MODEL_PATH}")
    
    # =========================================================================
    # FEATURE EXTRACTION
    # =========================================================================
    
    def extract_features(self, pick: Dict) -> Optional[np.ndarray]:
        """
        Extract feature vector from a pick dictionary.
        
        v2 Features: edge_pct, cv, hit_rate, trend, z_score, consistency,
                     stat_pts, stat_reb, stat_ast, is_over
        """
        try:
            # Core features
            edge_pct = pick.get('edge_pct', 0)
            cv = pick.get('cv', 0.3)
            
            # Hit rate
            filters = pick.get('filters', {})
            hit_rate_info = filters.get('hit_rate', {})
            hit_rate = hit_rate_info.get('hit_rate', 0.5) if isinstance(hit_rate_info, dict) else 0.5
            
            # Trend (L5 vs L10 performance)
            trend = pick.get('trend', 0)
            
            # Z-score (how far projection is from line in std devs)
            z_score = abs(pick.get('z_score', 0))
            
            # Consistency (1 - normalized std dev of L5)
            consistency = pick.get('consistency', 0.7)
            
            # Categorical encoding
            stat = pick.get('stat', 'pts')
            stat_pts = 1 if stat == 'pts' else 0
            stat_reb = 1 if stat == 'reb' else 0
            stat_ast = 1 if stat == 'ast' else 0
            is_over = 1 if pick.get('best_side') == 'OVER' else 0
            
            features = np.array([
                edge_pct,
                cv,
                hit_rate,
                trend,
                z_score,
                consistency,
                stat_pts,
                stat_reb,
                stat_ast,
                is_over,
            ], dtype=np.float32)
            
            return features
            
        except Exception as e:
            print(f"   ⚠️ Feature extraction error: {e}")
            return None
    
    # =========================================================================
    # TRAINING
    # =========================================================================
    
    def train(self, training_data: List[Dict]) -> Dict:
        """
        Train XGBoost model on historical pick data.
        
        Args:
            training_data: List of dicts with pick features and 'outcome' (1=win, 0=loss)
            
        Returns:
            Training metrics
        """
        if not XGBOOST_AVAILABLE:
            return {'error': 'XGBoost not installed'}
        
        if len(training_data) < 50:
            return {'error': f'Need at least 50 samples, got {len(training_data)}'}
        
        # Extract features and labels
        X = []
        y = []
        
        for pick in training_data:
            features = self.extract_features(pick)
            if features is not None and 'outcome' in pick:
                X.append(features)
                y.append(1 if pick['outcome'] == 'win' else 0)
        
        X = np.array(X)
        y = np.array(y)
        
        print(f"   📊 Training data: {len(X)} samples, {sum(y)} wins ({sum(y)/len(y)*100:.1f}%)")
        
        # Split 80/20
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        
        # Train model (precision focused)
        self.model = XGBClassifier(
            objective='binary:logistic',
            eval_metric='auc',
            max_depth=4,
            learning_rate=0.1,
            n_estimators=100,
            min_child_weight=3,  # Avoid overfitting
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
        )
        
        self.model.fit(X_train, y_train)
        self.is_loaded = True
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        y_pred_prob = self.model.predict_proba(X_test)[:, 1]
        
        accuracy = np.mean(y_pred == y_test)
        
        # Precision at different thresholds
        precision_55 = np.mean(y_test[y_pred_prob >= 0.55]) if sum(y_pred_prob >= 0.55) > 0 else 0
        precision_60 = np.mean(y_test[y_pred_prob >= 0.60]) if sum(y_pred_prob >= 0.60) > 0 else 0
        precision_68 = np.mean(y_test[y_pred_prob >= 0.68]) if sum(y_pred_prob >= 0.68) > 0 else 0
        
        # Feature importance
        importance = dict(zip(self.feature_names, self.model.feature_importances_))
        importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
        
        self._save_model()
        
        return {
            'samples': len(X),
            'train_size': len(X_train),
            'test_size': len(X_test),
            'accuracy': round(accuracy, 3),
            'precision_at_55': round(precision_55, 3),
            'precision_at_60': round(precision_60, 3),
            'precision_at_68': round(precision_68, 3),
            'feature_importance': {k: round(v, 3) for k, v in list(importance.items())[:5]},
        }
    
    # =========================================================================
    # PREDICTION / GATING
    # =========================================================================
    
    def predict_win_probability(self, pick: Dict) -> Optional[float]:
        """
        Predict win probability for a pick.
        
        Returns:
            Probability of winning (0-1), or None if model not loaded
        """
        if not self.is_loaded or not self.model:
            return None
        
        features = self.extract_features(pick)
        if features is None:
            return None
        
        try:
            prob = self.model.predict_proba(features.reshape(1, -1))[0][1]
            return float(prob)
        except Exception as e:
            print(f"   ⚠️ Prediction error: {e}")
            return None
    
    def should_approve(self, pick: Dict, tier: int = 2) -> Dict:
        """
        Determine if pick should be approved.
        
        Args:
            pick: Pick dictionary with features
            tier: Tier level (1, 2, or 3)
            
        Returns:
            Approval decision with reasoning
        """
        # If model not loaded, always approve (fail open)
        if not self.is_loaded:
            return {
                'approved': True,
                'reason': 'Model not loaded - fail open',
                'predicted_prob': None,
            }
        
        predicted_prob = self.predict_win_probability(pick)
        
        if predicted_prob is None:
            return {
                'approved': True,
                'reason': 'Could not predict - fail open',
                'predicted_prob': None,
            }
        
        threshold = self.thresholds.get(tier, 0.60)
        approved = predicted_prob >= threshold
        
        return {
            'approved': approved,
            'predicted_prob': round(predicted_prob, 3),
            'threshold': threshold,
            'tier': tier,
            'reason': f"{'✅ APPROVED' if approved else '❌ KILLED'}: {predicted_prob*100:.1f}% vs {threshold*100:.0f}% threshold"
        }
    
    def gate_picks(self, picks: List[Dict], tier: int = 2) -> List[Dict]:
        """
        Filter a list of picks through the gatekeeper.
        
        Returns only approved picks with gatekeeper metadata added.
        """
        if not self.is_loaded:
            # Return all with warning
            for p in picks:
                p['gatekeeper'] = {'approved': True, 'reason': 'Model not loaded'}
            return picks
        
        approved = []
        killed = 0
        
        for pick in picks:
            result = self.should_approve(pick, tier)
            pick['gatekeeper'] = result
            
            if result['approved']:
                approved.append(pick)
            else:
                killed += 1
        
        if killed > 0:
            print(f"   🚧 Gatekeeper: Approved {len(approved)}, Killed {killed}")
        
        return approved


# =============================================================================
# SYNTHETIC TRAINING DATA GENERATOR
# =============================================================================

def generate_synthetic_training_data(engine, n_days: int = 56):
    """
    Generate training data from historical backtesting.
    
    For each historical day, simulate props and check if they would have won.
    """
    from sqlalchemy import create_engine, text
    from datetime import datetime, timedelta
    
    DATABASE_URL = os.environ.get('DATABASE_URL',
        "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")
    
    db = create_engine(DATABASE_URL)
    training_data = []
    
    print(f"\n📊 Generating synthetic training data from {n_days} days of history...")
    
    # For each historical day
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=n_days)
    
    with db.connect() as conn:
        # Get all props with corresponding boxscores
        result = conn.execute(text("""
            SELECT 
                pp.player_name, pp.market, pp.line, pp.over_odds, pp.under_odds,
                pp.home_team, pp.away_team, pp.game_date,
                pb.pts, pb.reb, pb.ast
            FROM player_props pp
            JOIN player_boxscores pb ON 
                LOWER(TRIM(pp.player_name)) = LOWER(TRIM(pb.player_name))
                AND pp.game_date = pb.game_date
            WHERE pp.game_date BETWEEN :start AND :end
            AND pp.market IN ('player_points', 'player_rebounds', 'player_assists')
            ORDER BY pp.game_date DESC
        """), {'start': start_date.date(), 'end': end_date.date()})
        
        for row in result:
            r = dict(row._mapping)
            market = r['market']
            
            # Skip if line is missing
            if r['line'] is None:
                continue
                
            line = float(r['line'])
            
            # Map market to stat
            stat_map = {'player_points': 'pts', 'player_rebounds': 'reb', 'player_assists': 'ast'}
            stat = stat_map.get(market, 'pts')
            actual = float(r[stat]) if r[stat] else 0
            
            # Determine outcome for both OVER and UNDER
            for side in ['OVER', 'UNDER']:
                if side == 'OVER':
                    outcome = 'win' if actual > line else 'loss'
                    odds = r['over_odds'] or -110
                    edge_pct = ((actual - line) / line) * 100 if actual > line else 0
                else:
                    outcome = 'win' if actual < line else 'loss'
                    odds = r['under_odds'] or -110
                    edge_pct = ((line - actual) / line) * 100 if actual < line else 0
                
                # Create synthetic pick with estimated features
                pick = {
                    'player': r['player_name'],
                    'stat': stat,
                    'book_line': line,
                    'best_side': side,
                    'odds': odds,
                    'edge_pct': edge_pct,
                    'cv': 0.25,  # Estimated
                    'filters': {
                        'gp': 20,
                        'mpg': 28,
                        'hit_rate': {'hit_rate': 0.55},
                    },
                    'probabilities': {
                        'poisson': 0.5,  # Will be calculated
                    },
                    'outcome': outcome,
                }
                
                training_data.append(pick)
    
    print(f"   ✅ Generated {len(training_data)} training samples")
    wins = sum(1 for t in training_data if t['outcome'] == 'win')
    print(f"   Win rate: {wins/len(training_data)*100:.1f}%")
    
    return training_data


# =============================================================================
# TEST
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("XGBOOST GATEKEEPER v1.0 - TEST")
    print("=" * 70)
    
    gatekeeper = XGBoostGatekeeper()
    
    # Test pick
    test_pick = {
        'player': 'Anthony Edwards',
        'stat': 'pts',
        'book_line': 25.5,
        'best_side': 'UNDER',
        'odds': -110,
        'edge_pct': 15.0,
        'cv': 0.28,
        'filters': {
            'gp': 18,
            'mpg': 35.2,
            'hit_rate': {'hit_rate': 0.60},
        },
        'probabilities': {
            'raw': 0.65,
            'adjusted': 0.62,
            'poisson': 0.58,
        },
    }
    
    if gatekeeper.is_loaded:
        print("\n📊 Testing existing model:")
        result = gatekeeper.should_approve(test_pick, tier=2)
        print(f"   {result['reason']}")
    else:
        print("\n⚠️ No trained model found. Generate training data first:")
        print("   1. Run: python xgboost_gatekeeper.py --train")
        print("   2. Or call gatekeeper.train(training_data)")
    
    # If running with --train flag, generate and train
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--train':
        print("\n" + "=" * 70)
        print("TRAINING MODE")
        print("=" * 70)
        
        training_data = generate_synthetic_training_data(None, n_days=30)
        
        if len(training_data) >= 50:
            metrics = gatekeeper.train(training_data)
            print("\n📊 TRAINING RESULTS:")
            for k, v in metrics.items():
                print(f"   {k}: {v}")
        else:
            print(f"   ⚠️ Need more data: {len(training_data)} samples")
    
    print("\n" + "=" * 70)
    print("✅ XGBOOST GATEKEEPER v1.0 READY")
    print("=" * 70)
