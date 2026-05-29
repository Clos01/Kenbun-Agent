import json
import logging
import re
import decimal
from decimal import Decimal
import ast
import operator
from typing import Dict, Any, List, Optional

logger = logging.getLogger("wasm_interpreter")

# Configure Decimal context precision to standard 28 decimal places
decimal.getcontext().prec = 28

class SandboxSecurityException(Exception):
    """Raised when a declarative skill attempts a sandbox traversal or unsafe action."""
    pass

# Global constant operator mapping to prevent dynamic allocation within math actions
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: lambda x: x
}

class WASMSandboxInterpreter:
    """
    System 6.2: Sovereign WASM-style Declarative Sandbox Skill Interpreter.
    Evaluates JSON-based execution graphs safely and deterministically without raw Python `eval` or `exec`.
    """
    
    def __init__(self):
        self._state: Dict[str, Any] = {}
        # Pre-compiled, bounded safe math pattern allowing letters/identifiers for dynamic variables
        self._safe_math_pattern = re.compile(r"^[0-9+\-*/().\s$A-Za-z0-9_]+$")

    def _resolve_reference(self, arg: Any) -> Any:
        """Resolves state reference paths like '$step1.result' or nested dict items."""
        if not isinstance(arg, str) or not arg.startswith("$"):
            return arg
            
        path = arg[1:] # strip '$'
        parts = path.split(".")
        
        current = self._state
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def _resolve_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Iterates through arguments to resolve dynamic state references recursively."""
        resolved = {}
        for k, v in args.items():
            if isinstance(v, dict):
                resolved[k] = self._resolve_args(v)
            elif isinstance(v, list):
                resolved[k] = [self._resolve_reference(item) for item in v]
            else:
                resolved[k] = self._resolve_reference(v)
        return resolved

    # --- SAFE SANDBOX ACTIONS ---
    
    def _action_parse_json(self, args: Dict[str, Any]) -> Dict[str, Any]:
        text = args.get("text", "")
        return json.loads(text)

    def _action_get_key(self, args: Dict[str, Any]) -> Any:
        obj = args.get("object", {})
        key = args.get("key", "")
        default = args.get("default", None)
        if not isinstance(obj, dict):
            raise SandboxSecurityException("Action 'get_key' expects a dictionary object.")
        return obj.get(key, default)

    def _action_concat_strings(self, args: Dict[str, Any]) -> str:
        parts = args.get("parts", [])
        separator = args.get("separator", "")
        return separator.join([str(p) for p in parts])

    def _action_regex_match(self, args: Dict[str, Any]) -> bool:
        pattern = args.get("pattern", "")
        text = args.get("text", "")
        try:
            return bool(re.search(pattern, text))
        except re.error as e:
            raise SandboxSecurityException(f"Invalid regex pattern in sandbox: {e}")

    def _action_math(self, args: Dict[str, Any]) -> Decimal:
        expr = str(args.get("expression", ""))
        
        # Defense-in-Depth Step 1: Regex fast-fail check
        if not self._safe_math_pattern.match(expr):
            raise SandboxSecurityException("Math error: Formula violates sandbox character boundaries.")
            
        try:
            # Parse mathematical structure into AST
            tree = ast.parse(expr, mode='eval')
            
            # Defense-in-Depth Step 2: Recursive, depth-limited AST evaluator
            def safe_eval_ast(node: ast.AST, depth: int = 0) -> Decimal:
                if depth > 20:
                    raise SandboxSecurityException("Math error: Recursive depth limit exceeded.")
                    
                if isinstance(node, ast.Constant):
                    if isinstance(node.value, (int, float)):
                        return Decimal(str(node.value))
                    raise TypeError("Unsupported constant type.")
                elif isinstance(node, ast.Num): # Fallback compatibility for Python < 3.8
                    return Decimal(str(node.n))
                elif isinstance(node, ast.Name):
                    # Check first if name matches a resolved step result
                    val = self._resolve_reference(f"${node.id}.result")
                    if val is None:
                        # Direct reference fallback
                        val = self._resolve_reference(f"${node.id}")
                    if val is None:
                        raise ValueError(f"Undefined variable: {node.id}")
                    return Decimal(str(val))
                elif isinstance(node, ast.BinOp):
                    left = safe_eval_ast(node.left, depth + 1)
                    right = safe_eval_ast(node.right, depth + 1)
                    op_type = type(node.op)
                    
                    if op_type in SAFE_OPERATORS:
                        if op_type == ast.Div:
                            if right == 0:
                                raise ZeroDivisionError()
                            return left / right
                        return SAFE_OPERATORS[op_type](left, right)
                    raise TypeError("Unsupported binary operator.")
                elif isinstance(node, ast.UnaryOp):
                    operand = safe_eval_ast(node.operand, depth + 1)
                    op_type = type(node.op)
                    if op_type in SAFE_OPERATORS:
                        return SAFE_OPERATORS[op_type](operand)
                    raise TypeError("Unsupported unary operator.")
                raise TypeError("Unsupported expression syntax.")

            result = safe_eval_ast(tree.body)
            return result.normalize()
            
        except ZeroDivisionError:
            raise SandboxSecurityException("Math error: Division by zero is prohibited.")
        except (OverflowError, ArithmeticError):
            raise SandboxSecurityException("Math error: Numeric overflow or invalid arithmetic.")
        except Exception:
            raise SandboxSecurityException("Math error: Evaluation verification failed.")

    def execute_step(self, step: Dict[str, Any]) -> Any:
        """Executes a single declarative step safely."""
        step_id = step.get("id")
        action = step.get("action")
        raw_args = step.get("args", {})
        
        if not step_id or not action:
            raise ValueError("Steps must define both 'id' and 'action'.")
            
        # Resolve state references in arguments
        resolved_args = self._resolve_args(raw_args)
        
        # Action Routing
        handler_map = {
            "parse_json": self._action_parse_json,
            "get_key": self._action_get_key,
            "concat_strings": self._action_concat_strings,
            "regex_match": self._action_regex_match,
            "math": self._action_math
        }
        
        handler = handler_map.get(action)
        if not handler:
            raise SandboxSecurityException(f"Action '{action}' is not supported or forbidden in WASM Sandbox.")
            
        try:
            result = handler(resolved_args)
            
            # Convert Decimals to string/float representations for downstream usage
            if isinstance(result, Decimal):
                serializable_result = float(result)
            else:
                serializable_result = result
                
            self._state[step_id] = {"result": serializable_result}
            logger.info(f"✨ WASM Sandbox Step [{step_id}] succeeded.")
            return result
        except Exception as e:
            logger.error(f"❌ WASM Sandbox Step [{step_id}] failed: {e}")
            raise

    def execute_graph(self, graph_json: str) -> Dict[str, Any]:
        """
        Executes a complete declarative execution graph JSON payload.
        
        Args:
            graph_json: The serialized JSON skill blueprint.
            
        Returns:
            The complete terminal state and evaluation trace.
        """
        blueprint = json.loads(graph_json)
        self._state.clear()
        
        name = blueprint.get("name", "Unnamed Skill")
        steps = blueprint.get("steps", [])
        assertions = blueprint.get("assertions", [])
        
        logger.info(f"🚀 Executing Sandboxed WASM Skill: {name}")
        
        # 1. Run execution steps
        for step in steps:
            self.execute_step(step)
            
        # 2. Verify post-execution assertions
        assertion_results = []
        for assertion in assertions:
            left = self._resolve_reference(assertion.get("left"))
            right = self._resolve_reference(assertion.get("right"))
            op = assertion.get("operator", "equals")
            
            passed = False
            if op == "equals":
                passed = (left == right)
            elif op == "contains":
                passed = (right in left) if left else False
            elif op == "not_equals":
                passed = (left != right)
                
            assertion_results.append({
                "assertion": assertion,
                "passed": passed,
                "left_val": left,
                "right_val": right
            })
            
            if not passed:
                raise SandboxSecurityException(f"Assertion failed: {left} {op} {right}")
                
        return {
            "name": name,
            "trace": dict(self._state),
            "assertions": assertion_results,
            "status": "COMPLETED"
        }

if __name__ == "__main__":
    # Test Sandbox Execution Graph
    test_graph = {
        "name": "Compute Compound Metric",
        "steps": [
            {
                "id": "parse_payload",
                "action": "parse_json",
                "args": { "text": "{\"base_val\": 10, \"multiplier\": 5}" }
            },
            {
                "id": "get_multiplier",
                "action": "get_key",
                "args": { "object": "$parse_payload.result", "key": "multiplier" }
            },
            {
                "id": "compute_result",
                "action": "math",
                "args": { "expression": "100 * get_multiplier" }
            }
        ],
        "assertions": [
            { "left": "$compute_result.result", "operator": "equals", "right": 500.0 }
        ]
    }
    
    interpreter = WASMSandboxInterpreter()
    res = interpreter.execute_graph(json.dumps(test_graph))
    print("Execution Output:", json.dumps(res, indent=2))
