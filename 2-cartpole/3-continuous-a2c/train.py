import sys
import gym
import pylab
import numpy as np
import tensorflow as tf
from tensorflow_probability import distributions as tfd

EPISODES = 1000


# 정책 신경망과 가치 신경망 생성
class A2C(tf.keras.Model):
    def __init__(self, action_size):
        super(A2C, self).__init__()
        self.actor_fc1 = tf.keras.layers.Dense(24, activation='tanh')
        self.actor_mu = tf.keras.layers.Dense(action_size, 
            kernel_initializer=tf.keras.initializers.RandomUniform(minval=-3e-3, maxval=3e-5))
        self.actor_sigma = tf.keras.layers.Dense(action_size, activation='softplus',
            kernel_initializer=tf.keras.initializers.RandomUniform(minval=-3e-3, maxval=3e-5))
                            
        self.critic_fc1 = tf.keras.layers.Dense(24, activation='tanh')
        self.critic_fc2 = tf.keras.layers.Dense(24, activation='tanh')
        self.critic_out = tf.keras.layers.Dense(1, 
            kernel_initializer=tf.keras.initializers.RandomUniform(minval=-3e-3, maxval=3e-5))

    def call(self, x):
        actor_x = self.actor_fc1(x)
        mu = self.actor_mu(actor_x)
        sigma = self.actor_sigma(actor_x)
        sigma = sigma + 1e-5

        critic_x = self.critic_fc1(x)
        critic_x = self.critic_fc2(critic_x)
        value = self.critic_out(critic_x)
        return mu, sigma, value


# 카트폴 예제에서의 액터-크리틱(A2C) 에이전트
class A2CAgent:
    def __init__(self, action_size, max_action):
        self.render = False

        # 행동의 크기 정의
        self.action_size = action_size
        self.max_action = max_action

        # 액터-크리틱 하이퍼파라미터
        self.discount_factor = 0.99
        self.learning_rate = 0.001

        # 정책신경망과 가치신경망 생성
        self.model = A2C(self.action_size)
        # 최적화 알고리즘 설정, 미분값이 너무 커지는 현상을 막기 위해 clipnorm 설정
        self.optimizer = tf.keras.optimizers.Adam(lr=self.learning_rate, clipnorm=1.0)

    # 정책신경망의 출력을 받아 확률적으로 행동을 선택
    def get_action(self, state):
        mu, sigma, _ = self.model(state)
        dist = tfd.Normal(loc=mu[0], scale=sigma[0])
        action = dist.sample([1])[0]
        action = np.clip(action, -self.max_action, self.max_action)
        return action

    # 각 타임스텝마다 정책신경망과 가치신경망을 업데이트
    def train_model(self, state, action, reward, next_state, done):
        model_params = self.model.trainable_variables
        with tf.GradientTape() as tape:
            tape.watch(model_params)

            # 가치 신경망 오류 함수 구하기
            mu, sigma, value = self.model(state)
            _, _, next_value = self.model(next_state)
            target = reward + (1 - done) * self.discount_factor * next_value[0]
            critic_loss = 0.5 * tf.square(tf.stop_gradient(target) - value[0])
            critic_loss = tf.reduce_mean(critic_loss)

            # 정책 신경망 오류 함수 구하기
            advantage = tf.stop_gradient(target - value[0])
            dist = tfd.Normal(loc=mu, scale=sigma)
            action_prob = dist.prob([action])[0]
            actor_loss = -tf.math.log(action_prob + 1e-5) * advantage
            actor_loss = tf.reduce_mean(actor_loss)

            # 하나의 오류 함수로 만들기
            loss = 0.1 * actor_loss + critic_loss

        # 오류함수를 줄이는 방향으로 모델 업데이트
        grads = tape.gradient(loss, model_params)
        self.optimizer.apply_gradients(zip(grads, model_params))
        return np.array(loss), np.array(actor_loss), np.array(critic_loss), np.array(entropy)


if __name__ == "__main__":
    # CartPole-v1 환경, 최대 타임스텝 수가 500
    gym.envs.register(
        id='CartPoleContinuous-v0',
        entry_point='env:ContinuousCartPoleEnv',
        max_episode_steps=500,
        reward_threshold=475.0)

    env = gym.make('CartPoleContinuous-v0')
    # 환경으로부터 상태와 행동의 크기를 받아옴
    state_size = env.observation_space.shape[0]
    action_size = env.action_space.shape[0]
    max_action = env.action_space.high[0]

    # 액터-크리틱(A2C) 에이전트 생성
    agent = A2CAgent(action_size, max_action)

    scores, episodes = [], []
    score_avg = 0

    for e in range(EPISODES):
        done = False
        score = 0
        loss_list = []
        state = env.reset()
        state = np.reshape(state, [1, state_size])

        while not done:
            if agent.render:
                env.render()

            action = agent.get_action(state)
            next_state, reward, done, info = env.step(action)
            next_state = np.reshape(next_state, [1, state_size])

            # 타임스텝마다 보상 0.1, 에피소드가 중간에 끝나면 -1 보상
            score += reward
            reward = 0.1 if not done or score == 500 else -1

            # 매 타임스텝마다 학습
            loss = agent.train_model(state, action, reward, next_state, done)
            loss_list.append(loss)
            state = next_state

            if done:
                # 에피소드마다 학습 결과 출력
                score_avg = 0.9 * score_avg + 0.1 * score if score_avg != 0 else score
                scores.append(score_avg)
                episodes.append(e)
                loss_list = np.array(loss_list)

                pylab.plot(episodes, scores, 'b')
                pylab.savefig("./save_graph/a2c.png")
                print("episode: {:3d} | score avg: {:3.2f} | loss: {:.3f} ".format(
                      e, score_avg, np.mean(loss_list)))

                # 이동 평균이 350 이상일 때 종료
                if score_avg > 350:
                    agent.model.save_weights("./save_model/a2c", save_format="tf")
                    sys.exit()

        if e % 50 == 0:
            agent.model.save_weights("./save_model/a2c", save_format="tf")