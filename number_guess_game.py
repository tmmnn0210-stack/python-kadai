"""1～100の乱数を当てる数当てゲーム"""

import random

secret = random.randint(1, 100)
attempts = 0

print("1～100の間の数字を当ててください。")

while True:
    try:
        guess = int(input("数字を入力してください: ").strip())
    except ValueError:
        print("整数を入力してください。")
        continue

    if guess < 1 or guess > 100:
        print("1～100の範囲で入力してください。")
        continue

    attempts += 1

    if guess == secret:
        print(f"正解です！試行回数は {attempts} 回でした。")
        break
    if guess < secret:
        print("もっと大きい")
    else:
        print("もっと小さい")
