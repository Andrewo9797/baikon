"""
Baikon Engine - Simple but working version
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional
from parser import BaikonParser, FlowModule, Flow, FlowFunction, FlowAction, FlowTrigger, ActionType, TriggerType


class FlowContext:
    """Execution context for flows"""
    def __init__(self):
        self.variables = {}
        self.start_time = time.time()


class BaikonEngine:
    def __init__(self, config: Dict[str, Any] = None):
        self.parser = BaikonParser()
        self.modules = {}
        self.config = config or {}
        
        # Set up logging
        logging.basicConfig(
            level=getattr(logging, self.config.get('log_level', 'INFO').upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('BaikonEngine')
    
    def load_module(self, filepath: str, module_name: str = None) -> bool:
        """Load a flow module"""
        try:
            module = self.parser.parse_file(filepath)
            
            if module_name:
                module.name = module_name
            
            self.modules[module.name] = module
            
            self.logger.info(f"Loaded module: {module.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading module {filepath}: {e}")
            return False
    
    async def create_context(self, user_id: str = None, session_id: str = None) -> FlowContext:
        """Create execution context"""
        context = FlowContext()
        
        # Load variables from modules
        for module in self.modules.values():
            for var_name, var_def in module.variables.items():
                context.variables[var_name] = var_def.value
        
        return context
    
    async def process_input(self, user_input: str, context: FlowContext = None) -> List[str]:
        """Process user input and return responses"""
        if context is None:
            context = await self.create_context()
        
        responses = []
        user_input = user_input.strip().lower()
        
        # Find matching flows
        for module in self.modules.values():
            for flow_name, flow in module.flows.items():
                for trigger in flow.triggers:
                    if self._match_trigger(user_input, trigger):
                        # Get the function to call
                        func_name = self.parser.get_function_for_trigger(flow_name, trigger.pattern)
                        if func_name and func_name in module.functions:
                            self.logger.info(f"Executing flow: {flow_name}")
                            result = await self._call_function(module.functions[func_name], module, context)
                            if result:
                                responses.extend(result)
                            self.logger.info(f"Flow {flow_name} completed")
        
        return responses
    
    def _match_trigger(self, user_input: str, trigger: FlowTrigger) -> bool:
        """Check if user input matches a trigger"""
        if trigger.type == TriggerType.USER_SAYS:
            pattern = trigger.pattern.lower().strip()
            user_input_lower = user_input.lower().strip()
            
            # Exact match
            if user_input_lower == pattern:
                return True
            
            # Wildcard matching
            if '*' in pattern:
                # Simple wildcard support
                if pattern.startswith('*') and pattern.endswith('*'):
                    search_term = pattern[1:-1]
                    return search_term in user_input_lower
                elif pattern.startswith('*'):
                    return user_input_lower.endswith(pattern[1:])
                elif pattern.endswith('*'):
                    return user_input_lower.startswith(pattern[:-1])
            
            return False
        
        return False
    
    async def _call_function(self, function: FlowFunction, module: FlowModule, context: FlowContext) -> List[str]:
        """Call a function"""
        responses = []
        
        for action in function.actions:
            result = await self._execute_action(action, context)
            if result:
                responses.append(result)
        
        return responses
    
    async def _execute_action(self, action: FlowAction, context: FlowContext) -> Optional[str]:
        """Execute a single action"""
        if action.type == ActionType.SAY:
            message = action.params['message']
            # Substitute variables
            message = self._substitute_variables(message, context)
            return message
        
        elif action.type == ActionType.SET:
            var_name = action.params['variable']
            value = action.params['value']
            
            # Handle arithmetic
            if isinstance(value, str) and '+' in value:
                try:
                    parts = value.split('+')
                    if len(parts) == 2:
                        left = parts[0].strip()
                        right = parts[1].strip()
                        
                        # If left side is a variable
                        if left in context.variables:
                            left_val = context.variables[left]
                            if isinstance(left_val, int) and right.isdigit():
                                value = left_val + int(right)
                except:
                    pass
            
            context.variables[var_name] = value
            return None
        
        return None
    
    def _substitute_variables(self, text: str, context: FlowContext) -> str:
        """Substitute variables in text using {variable_name} syntax"""
        for var_name, value in context.variables.items():
            placeholder = f'{{{var_name}}}'
            if placeholder in text:
                text = text.replace(placeholder, str(value))
        return text
    
    def get_module_info(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a loaded module"""
        if module_name in self.modules:
            module = self.modules[module_name]
            return {
                'name': module.name,
                'flows': list(module.flows.keys()),
                'functions': list(module.functions.keys()),
                'variables': list(module.variables.keys()),
                'imports': module.imports or [],
                'config': module.config or {}
            }
        return None
    
    def list_modules(self) -> List[str]:
        """List all loaded modules"""
        return list(self.modules.keys())


async def main():
    """Test the engine"""
    engine = BaikonEngine({'log_level': 'INFO'})
    
    # Test content
    test_content = """
flow assistant:
    when user says "hello" -> call greet_user
    when user says "help" -> call show_help

function greet_user:
    set conversation_count = conversation_count + 1
    say "Hello {user_name}! This is conversation #{conversation_count}."

function show_help:
    say "I can help you with greetings and more!"
"""
    
    # Parse and load
    module = engine.parser.parse_content(test_content, "test")
    engine.modules["test"] = module
    
    # Test
    context = await engine.create_context()
    
    test_inputs = ["hello", "help", "goodbye"]
    
    for user_input in test_inputs:
        print(f"\nUser: {user_input}")
        responses = await engine.process_input(user_input, context)
        for response in responses:
            print(f"Bot: {response}")


if __name__ == "__main__":
    asyncio.run(main())