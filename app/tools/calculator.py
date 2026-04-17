import re


def calculator(expression: str) -> str:
    """
    Safely evaluates a mathematical expression.
    """
    clean_expr = expression.replace(" ", "")

    # SECURITY GATE: Only allow numbers, decimals, and basic math operators.
    # This completely blocks malicious inputs like: __import__('os').system('rm -rf /')
    if not re.match(r"^[\d\.\+\-\*\/\(\)]+$", clean_expr):
        return "Observation: Error - Invalid characters in math expression. Only numbers and + - * / ( ) are allowed."

    try:
        # eval is safe here ONLY because the regex above guarantees no letters or built-ins exist
        # We also pass empty dictionaries for globals and locals for a secondary layer of security
        result = eval(clean_expr, {"__builtins__": None}, {})

        # Format the output nicely (e.g., convert 15296.0 to 15296)
        if isinstance(result, float):
            return f"Observation: {result:g}"

        return f"Observation: {str(result)}"

    except ZeroDivisionError:
        return "Observation: Error - Division by zero is undefined."
    except SyntaxError:
        return "Observation: Error - Invalid math syntax."
    except Exception as e:
        return f"Observation: Error calculating: {str(e)}"
