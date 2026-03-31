"""2つの数値と四則演算子を入力し、結果を表示する簡単な計算機"""

a = float(input("1つ目の数値を入力してください: "))
b = float(input("2つ目の数値を入力してください: "))
op = input("演算子を入力してください (+, -, *, /): ").strip()

if op == "+":
    result = a + b
elif op == "-":
    result = a - b
elif op == "*":
    result = a * b
elif op == "/":
    if b == 0:
        print("エラー: 0では割れません。")
        raise SystemExit(1)
    result = a / b
else:
    print("エラー: +, -, *, / のいずれかを入力してください。")
    raise SystemExit(1)

print(f"結果: {result}")
