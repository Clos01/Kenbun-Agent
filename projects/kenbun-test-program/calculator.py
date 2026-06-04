#!/usr/bin/env python3
import argparse
import sys

def add(x, y):
    return x + y

def subtract(x, y):
    return x - y

def multiply(x, y):
    return x * y

def divide(x, y):
    if y == 0:
        raise ValueError("Cannot divide by zero")
    return x / y

def main():
    parser = argparse.ArgumentParser(
        description="A professional CLI calculator.",
        epilog="Examples:\n  calculator.py add 5 10\n  calculator.py divide 100 4",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="operation", help="Math operations", required=True)
    
    # Subparser template for operations
    def add_operation(name, help_text):
        p = subparsers.add_parser(name, help=help_text)
        p.add_argument("x", type=float, help="First number")
        p.add_argument("y", type=float, help="Second number")
    
    add_operation("add", "Add two numbers")
    add_operation("subtract", "Subtract the second number from the first")
    add_operation("multiply", "Multiply two numbers")
    add_operation("divide", "Divide the first number by the second")
    
    args = parser.parse_args()
    
    try:
        if args.operation == "add":
            result = add(args.x, args.y)
        elif args.operation == "subtract":
            result = subtract(args.x, args.y)
        elif args.operation == "multiply":
            result = multiply(args.x, args.y)
        elif args.operation == "divide":
            result = divide(args.x, args.y)
            
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
