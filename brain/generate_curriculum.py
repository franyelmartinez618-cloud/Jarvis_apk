"""Generate deterministic, exactly-solvable original reasoning exercises."""
import argparse
import json
import random
from fractions import Fraction
from pathlib import Path


def fmt(value):
    if isinstance(value, Fraction):
        if value.denominator == 1:
            return str(value.numerator)
        return f"{value.numerator}/{value.denominator}"
    return str(value)


def is_prime(n):
    if n < 2:
        return False
    divisor = 2
    while divisor * divisor <= n:
        if n % divisor == 0:
            return False
        divisor += 1
    return True


def make_examples(count, seed):
    rng = random.Random(seed)
    examples = []
    for index in range(count):
        kind = index % 10
        if kind == 0:
            a, b = rng.randint(-9999, 9999), rng.randint(-9999, 9999)
            question, answer = f"Calcula {a} + ({b}).", f"{a} + ({b}) = {a + b}."
        elif kind == 1:
            a, b = rng.randint(-9999, 9999), rng.randint(-9999, 9999)
            question, answer = f"Calcula {a} - ({b}).", f"{a} - ({b}) = {a - b}."
        elif kind == 2:
            a, b = rng.randint(-300, 300), rng.randint(-300, 300)
            question, answer = f"Calcula {a} por {b}.", f"{a} × {b} = {a * b}."
        elif kind == 3:
            divisor, quotient = rng.choice([i for i in range(-50, 51) if i]), rng.randint(-100, 100)
            dividend = divisor * quotient
            question, answer = f"Divide {dividend} entre {divisor}.", f"{dividend} ÷ {divisor} = {quotient}; la división es exacta."
        elif kind == 4:
            base, percent = rng.randint(1, 10000), rng.choice([5, 10, 12.5, 20, 25, 40, 50, 75])
            result = Fraction(str(percent)) * base / 100
            question = f"¿Cuánto es el {fmt(Fraction(str(percent)))} por ciento de {base}?"
            answer = f"El {fmt(Fraction(str(percent)))} % de {base} es {fmt(result)}."
        elif kind == 5:
            x, coefficient, offset = rng.randint(-50, 50), rng.choice([i for i in range(-12, 13) if i]), rng.randint(-100, 100)
            result = coefficient * x + offset
            question = f"Resuelve {coefficient}x + ({offset}) = {result}."
            answer = f"Restando {offset}: {coefficient}x = {result - offset}. Dividiendo entre {coefficient}: x = {x}."
        elif kind == 6:
            numerator, denominator = rng.randint(1, 200), rng.randint(1, 100)
            value = Fraction(numerator, denominator)
            question = f"Simplifica la fracción {numerator}/{denominator}."
            answer = f"Dividiendo numerador y denominador por su máximo común divisor, {numerator}/{denominator} = {fmt(value)}."
        elif kind == 7:
            values = [rng.randint(-100, 100) for _ in range(rng.randint(3, 6))]
            total = sum(values)
            question = f"Calcula la media aritmética de {', '.join(map(str, values))}."
            answer = f"La suma es {total}; hay {len(values)} valores. La media es {fmt(Fraction(total, len(values)))}."
        elif kind == 8:
            number = rng.randint(2, 2000)
            question = f"¿El número {number} es primo?"
            answer = f"{number} {'es' if is_prime(number) else 'no es'} primo: {'solo tiene como divisores positivos 1 y él mismo' if is_prime(number) else 'tiene divisores positivos distintos de 1 y de sí mismo'}."
        else:
            values = [rng.randint(-99, 99) for _ in range(5)]
            ordered = sorted(values)
            question = f"Ordena de menor a mayor: {', '.join(map(str, values))}."
            answer = f"El orden ascendente es: {', '.join(map(str, ordered))}."

        examples.append({
            "text": f"### Usuario:\n{question}\n### JARVIS:\n{answer}",
            "origin": "JARVIS deterministic synthetic curriculum",
            "category": [
                "addition", "subtraction", "multiplication", "division", "percentages",
                "linear_equations", "fractions", "averages", "primality", "sorting"
            ][kind],
        })
    return examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/seed/zz_generated_curriculum.jsonl")
    parser.add_argument("--count", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=20261030)
    args = parser.parse_args()
    if args.count < 100 or args.count > 100000:
        raise SystemExit("--count debe estar entre 100 y 100000.")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    examples = make_examples(args.count, args.seed)
    with output.open("w", encoding="utf-8") as stream:
        for item in examples:
            stream.write(json.dumps({"text": item["text"]}, ensure_ascii=False) + "\n")
    print(f"Generados {len(examples):,} ejercicios exactos y reproducibles: {output}")


if __name__ == "__main__":
    main()
