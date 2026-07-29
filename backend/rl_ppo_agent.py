"""
PPO Reinforcement Learning Trading Agent v1.0
===============================================
Proximal Policy Optimization for trade decision-making.
Actor-Critic architecture trained on historical OANDA data.
"""
import logging
import numpy as np
import os
import json
from typing import Dict, List, Optional
from datetime import datetime, timezone
from collections import deque

logger = logging.getLogger(__name__)

try:
    import ml_config
except ImportError:
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    tf.config.set_visible_devices([], 'GPU')
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False


class TradingEnvironment:
    """
    Simplified trading environment for RL training.
    State: 13 technical features (same as LSTM/GRU system)
    Actions: 0=HOLD, 1=BUY, 2=SELL
    Reward: profit/loss from trade
    """
    LOOKBACK = 20
    COST = 0.0001  # transaction cost (1 pip spread)

    def __init__(self, features: np.ndarray, closes: np.ndarray):
        self.features = features
        self.closes = closes
        self.n = len(features)
        self.idx = self.LOOKBACK
        self.position = 0  # 0=flat, 1=long, -1=short
        self.entry_price = 0.0
        self.total_reward = 0.0
        self.trades = 0
        self.wins = 0

    def reset(self):
        self.idx = self.LOOKBACK
        self.position = 0
        self.entry_price = 0.0
        self.total_reward = 0.0
        self.trades = 0
        self.wins = 0
        return self._get_state()

    def _get_state(self):
        start = max(0, self.idx - self.LOOKBACK)
        state = self.features[start:self.idx].flatten()
        # Pad position info
        pos_info = np.array([self.position, self.total_reward / 100.0], dtype=np.float32)
        return np.concatenate([state, pos_info])

    @property
    def state_dim(self):
        return self.LOOKBACK * self.features.shape[1] + 2

    def step(self, action):
        """Execute action, return (next_state, reward, done).

        Iter 84 — reward shaping upgrades:
        - Amplified PnL signal (100 → 200) so wins/losses register clearly.
        - Small **entropy bonus** for BUY/SELL actions to prevent policy
          collapse to always-HOLD (the #1 cause of our 29% collapse).
        - Larger **penalty** for holding an open losing position rather than a
          symmetric unrealized reward, which biased the agent toward passive
          floating losses.
        - Winning trades get a bonus multiplier — the goal is win RATE, not
          raw PnL, for a binary-options-style objective.
        """
        price = self.closes[self.idx]
        reward = 0.0

        # Action: 0=HOLD, 1=BUY, 2=SELL
        if action == 1 and self.position <= 0:
            # Open long or close short
            if self.position == -1:
                pnl = (self.entry_price - price) / (self.entry_price + 1e-10) - self.COST
                reward = pnl * 200
                # Win-rate bonus: extra reward for correct short → long flips
                if pnl > 0:
                    reward += 0.5
                self.trades += 1
                if pnl > 0:
                    self.wins += 1
            self.position = 1
            self.entry_price = price
            # Tiny exploration bonus for taking action (offsets HOLD default)
            reward += 0.02

        elif action == 2 and self.position >= 0:
            # Open short or close long
            if self.position == 1:
                pnl = (price - self.entry_price) / (self.entry_price + 1e-10) - self.COST
                reward = pnl * 200
                if pnl > 0:
                    reward += 0.5
                self.trades += 1
                if pnl > 0:
                    self.wins += 1
            self.position = -1
            self.entry_price = price
            reward += 0.02

        elif action == 0:
            # ASYMMETRIC unrealized handling — small penalty for sitting on a
            # loser (encourages the agent to CLOSE bad positions) but no
            # reward for sitting on a winner (the actual close-reward is
            # what should teach it). This kills the "always hold" attractor.
            if self.position != 0:
                unrealized = 0.0
                if self.position == 1:
                    unrealized = (price - self.entry_price) / (self.entry_price + 1e-10)
                else:
                    unrealized = (self.entry_price - price) / (self.entry_price + 1e-10)
                if unrealized < 0:
                    reward = unrealized * 20  # 2× the old penalty
                # If unrealized > 0, reward stays 0 → agent must actually
                # close the trade to bank the win.
            else:
                # Small negative reward for sitting flat forever
                reward = -0.001

        self.total_reward += reward
        self.idx += 1
        done = self.idx >= self.n - 1

        # Close position at end
        if done and self.position != 0:
            if self.position == 1:
                pnl = (price - self.entry_price) / (self.entry_price + 1e-10) - self.COST
            else:
                pnl = (self.entry_price - price) / (self.entry_price + 1e-10) - self.COST
            reward += pnl * 200
            if pnl > 0:
                reward += 0.5
            self.trades += 1
            if pnl > 0:
                self.wins += 1
            self.position = 0

        return self._get_state(), reward, done


class PPOAgent:
    """
    PPO Actor-Critic agent for trading decisions.
    """

    def __init__(self):
        self.actor = None
        self.critic = None
        self.is_trained = False
        self.accuracy = 0.0
        self.training_stats = {}
        self.total_predictions = 0
        self.model_dir = '/app/backend/models/ppo'
        self.stats_path = '/app/backend/models/ppo_stats.json'
        self.gamma = 0.99
        self.lam = 0.95
        self.clip_ratio = 0.2
        self.actor_lr = 3e-4
        self.critic_lr = 1e-3
        self.state_dim = None
        self._load_stats()
        # Try to load saved models after loading stats
        if self.is_trained and self.state_dim:
            self._try_load()

    def _build(self, state_dim: int):
        self.state_dim = state_dim

        # Actor (policy)
        actor_inp = layers.Input(shape=(state_dim,))
        x = layers.Dense(128, activation='relu')(actor_inp)
        x = layers.Dense(64, activation='relu')(x)
        x = layers.Dense(3, activation='softmax')(x)  # HOLD, BUY, SELL
        self.actor = keras.Model(inputs=actor_inp, outputs=x)
        self.actor.compile(optimizer=keras.optimizers.Adam(self.actor_lr))

        # Critic (value)
        critic_inp = layers.Input(shape=(state_dim,))
        x = layers.Dense(128, activation='relu')(critic_inp)
        x = layers.Dense(64, activation='relu')(x)
        x = layers.Dense(1)(x)
        self.critic = keras.Model(inputs=critic_inp, outputs=x)
        self.critic.compile(optimizer=keras.optimizers.Adam(self.critic_lr), loss='mse')

        logger.info(f"PPO agent built: state_dim={state_dim}, Actor(128→64→3), Critic(128→64→1)")

    def _load_stats(self):
        if os.path.exists(self.stats_path):
            try:
                with open(self.stats_path) as f:
                    stats = json.load(f)
                self.training_stats = stats.get('training_stats', {})
                self.accuracy = stats.get('accuracy', 0)
                self.total_predictions = stats.get('total_predictions', 0)
                self.is_trained = stats.get('is_trained', False)
                self.state_dim = stats.get('state_dim', None)
            except Exception:
                pass

    def _save_stats(self):
        os.makedirs(os.path.dirname(self.stats_path), exist_ok=True)
        with open(self.stats_path, 'w') as f:
            json.dump({
                'accuracy': self.accuracy,
                'total_predictions': self.total_predictions,
                'is_trained': self.is_trained,
                'state_dim': self.state_dim,
                'training_stats': self.training_stats
            }, f)

    def _try_load(self):
        actor_path = os.path.join(self.model_dir, 'actor.keras')
        critic_path = os.path.join(self.model_dir, 'critic.keras')
        if os.path.exists(actor_path) and os.path.exists(critic_path):
            try:
                self.actor = keras.models.load_model(actor_path)
                self.critic = keras.models.load_model(critic_path)
                self.is_trained = True
                logger.info("Loaded PPO models")
                return True
            except Exception as e:
                logger.warning(f"Could not load PPO models: {e}")
        return False

    def _save_models(self):
        os.makedirs(self.model_dir, exist_ok=True)
        self.actor.save(os.path.join(self.model_dir, 'actor.keras'))
        self.critic.save(os.path.join(self.model_dir, 'critic.keras'))

    def _compute_gae(self, rewards, values, dones):
        """Generalized Advantage Estimation."""
        n = len(rewards)
        advantages = np.zeros(n)
        last_gae = 0
        for t in reversed(range(n)):
            next_val = values[t + 1] if t + 1 < len(values) else 0
            delta = rewards[t] + self.gamma * next_val * (1 - dones[t]) - values[t]
            advantages[t] = last_gae = delta + self.gamma * self.lam * (1 - dones[t]) * last_gae
        returns = advantages + np.array(values[:n])
        return advantages, returns

    def train(self, features: np.ndarray, closes: np.ndarray,
              n_episodes: int = 20, ppo_epochs: int = 4) -> Dict:
        """Train PPO agent on historical data."""
        if not TF_AVAILABLE:
            return {'success': False, 'error': 'TensorFlow not available'}

        env = TradingEnvironment(features, closes)

        # Iter 66: if incoming feature dim differs from saved model's state_dim,
        # rebuild from scratch and DO NOT reload old weights (which would have
        # the wrong shape and crash on first forward pass).
        dim_changed = self.state_dim is not None and self.state_dim != env.state_dim
        if self.actor is None or dim_changed:
            if dim_changed:
                logger.info(f"PPO rebuild: state_dim {self.state_dim} → {env.state_dim} (feature count changed). Starting fresh.")
            self._build(env.state_dim)
            # Only try loading when the dim actually matched (fresh process boot)
            if not dim_changed:
                self._try_load()

        episode_rewards = []
        episode_win_rates = []

        for ep in range(n_episodes):
            # Collect trajectory
            states, actions, rewards, dones, old_probs = [], [], [], [], []
            state = env.reset()

            while True:
                s = np.array(state, dtype=np.float32).reshape(1, -1)
                s = np.nan_to_num(s, nan=0.0, posinf=1.0, neginf=-1.0)

                probs = self.actor.predict(s, verbose=0)[0]
                action = np.random.choice(3, p=probs)

                states.append(s[0])
                actions.append(action)
                old_probs.append(probs[action])

                next_state, reward, done = env.step(action)
                rewards.append(reward)
                dones.append(float(done))
                state = next_state

                if done:
                    break

            episode_rewards.append(env.total_reward)
            win_rate = (env.wins / max(env.trades, 1)) * 100
            episode_win_rates.append(win_rate)

            # Convert to arrays
            states_arr = np.array(states, dtype=np.float32)
            states_arr = np.nan_to_num(states_arr, nan=0.0, posinf=1.0, neginf=-1.0)
            actions_arr = np.array(actions, dtype=np.int32)
            rewards_arr = np.array(rewards, dtype=np.float32)
            dones_arr = np.array(dones, dtype=np.float32)
            old_probs_arr = np.array(old_probs, dtype=np.float32)

            # Compute values and GAE
            values = self.critic.predict(states_arr, verbose=0).flatten().tolist()
            advantages, returns = self._compute_gae(rewards_arr, values, dones_arr)
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

            # PPO update
            for _ in range(ppo_epochs):
                # Actor update
                with tf.GradientTape() as tape:
                    new_probs_all = self.actor(states_arr, training=True)
                    indices = tf.stack([tf.range(len(actions_arr)), actions_arr], axis=1)
                    new_probs = tf.gather_nd(new_probs_all, indices)

                    ratio = new_probs / (old_probs_arr + 1e-8)
                    clipped = tf.clip_by_value(ratio, 1 - self.clip_ratio, 1 + self.clip_ratio)
                    actor_loss = -tf.reduce_mean(tf.minimum(
                        ratio * advantages,
                        clipped * advantages
                    ))

                actor_grads = tape.gradient(actor_loss, self.actor.trainable_variables)
                self.actor.optimizer.apply_gradients(zip(actor_grads, self.actor.trainable_variables))

                # Critic update
                self.critic.fit(states_arr, np.array(returns, dtype=np.float32),
                                epochs=1, verbose=0, batch_size=64)

            if (ep + 1) % 5 == 0:
                logger.info(f"  PPO Episode {ep+1}/{n_episodes}: reward={env.total_reward:.2f}, "
                            f"trades={env.trades}, win_rate={win_rate:.1f}%")

        self.is_trained = True
        self._save_models()

        avg_reward = np.mean(episode_rewards[-5:])
        avg_win_rate = np.mean(episode_win_rates[-5:])
        self.accuracy = avg_win_rate

        self.training_stats = {
            'avg_reward': round(float(avg_reward), 2),
            'avg_win_rate': round(float(avg_win_rate), 2),
            'total_episodes': n_episodes,
            'final_trades': env.trades,
            'trained_at': datetime.now(timezone.utc).isoformat()
        }
        self._save_stats()

        logger.info(f"PPO training complete: avg_reward={avg_reward:.2f}, win_rate={avg_win_rate:.1f}%")
        return {
            'success': True,
            'avg_reward': round(float(avg_reward), 2),
            'avg_win_rate': round(float(avg_win_rate), 2),
            'episodes': n_episodes
        }

    def predict(self, features: np.ndarray) -> Optional[Dict]:
        """Predict action from current state features."""
        if not TF_AVAILABLE or self.actor is None:
            return None

        # Build state: flatten last LOOKBACK features + position info
        lookback = TradingEnvironment.LOOKBACK
        if len(features) < lookback:
            return None

        recent = features[-lookback:].flatten()
        pos_info = np.array([0.0, 0.0], dtype=np.float32)  # flat position, no pnl
        state = np.concatenate([recent, pos_info]).reshape(1, -1).astype(np.float32)
        state = np.nan_to_num(state, nan=0.0, posinf=1.0, neginf=-1.0)

        probs = self.actor.predict(state, verbose=0)[0]
        action = int(np.argmax(probs))

        action_map = {0: 'HOLD', 1: 'BUY', 2: 'SELL'}
        self.total_predictions += 1

        return {
            'direction': action_map[action],
            'confidence': round(float(probs[action]) * 100, 2),
            'probabilities': {
                'HOLD': round(float(probs[0]) * 100, 2),
                'BUY': round(float(probs[1]) * 100, 2),
                'SELL': round(float(probs[2]) * 100, 2)
            },
            'method': 'PPO_RL',
            'model_trained': self.is_trained
        }

    def get_stats(self) -> Dict:
        return {
            'model_type': 'PPO Actor-Critic',
            'is_trained': self.is_trained,
            'accuracy': round(self.accuracy, 2),
            'total_predictions': self.total_predictions,
            'training_stats': self.training_stats
        }


# Global instance
ppo_agent = PPOAgent()
