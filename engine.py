"""
Baikon Engine v2.0 - Advanced execution engine with async support, 
middleware, variables, and external integrations
"""

import asyncio
import json
import time
import logging
import re
import requests
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import asdict
from parser import BaikonParser, FlowModule, Flow, FlowFunction, FlowAction, FlowTrigger, ActionType, TriggerType


class FlowContext:
    """Execution context for flows"""
    def __init__(self):
        self.variables = {}
        self.session_data = {}
        self.user_data = {}
        self.api_responses = {}
        self.events = []
        self.middleware_stack = []
        self.start_time = time.time()
        self.request_id = None


class FlowMiddleware:
    """Base class for middleware"""
    def __init__(self, name: str):
        self.name = name
    
    async def before_flow(self, context: FlowContext, flow: Flow) -> bool:
        """Execute before flow. Return False to stop execution"""
        return True
    
    async def after_flow(self, context: FlowContext, flow: Flow, result: Any) -> Any:
        """Execute after flow"""
        return result
    
    async def on_error(self, context: FlowContext, error: Exception) -> bool:
        """Handle errors. Return True if handled"""
        return False


class BaikonEngine:
    def __init__(self, config: Dict[str, Any] = None):
        self.parser = BaikonParser()
        self.modules = {}
        self.contexts = {}
        self.middleware = {}
        self.timers = {}
        self.event_handlers = {}
        self.api_clients = {}
        self.config = config or {}
        
        # Set up logging
        logging.basicConfig(
            level=getattr(logging, self.config.get('log_level', 'INFO').upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('BaikonEngine')
        
        # Built-in middleware
        self._register_builtin_middleware()
        
        # Event loop for async operations
        self.loop = None
        self.running = False
    
    def _register_builtin_middleware(self):
        """Register built-in middleware"""
        class LoggingMiddleware(FlowMiddleware):
            def __init__(self, engine):
                super().__init__("logging")
                self.engine = engine
            
            async def before_flow(self, context: FlowContext, flow: Flow) -> bool:
                self.engine.logger.info(f"Executing flow: {flow.name}")
                return True
            
            async def after_flow(self, context: FlowContext, flow: Flow, result: Any) -> Any:
                self.engine.logger.info(f"Flow {flow.name} completed")
                return result
        
        class RateLimitMiddleware(FlowMiddleware):
            def __init__(self, engine):
                super().__init__("rate_limit")
                self.engine = engine
                self.request_counts = {}
            
            async def before_flow(self, context: FlowContext, flow: Flow) -> bool:
                # Simple rate limiting - can be enhanced
                user_id = context.user_data.get('id', 'anonymous')
                now = time.time()
                
                if user_id not in self.request_counts:
                    self.request_counts[user_id] = []
                
                # Remove old requests (older than 1 minute)
                self.request_counts[user_id] = [
                    req_time for req_time in self.request_counts[user_id] 
                    if now - req_time < 60
                ]
                
                # Check limit
                limit = self.engine.config.get('rate_limit', 60)
                if len(self.request_counts[user_id]) >= limit:
                    self.engine.logger.warning(f"Rate limit exceeded for user {user_id}")
                    return False
                
                self.request_counts[user_id].append(now)
                return True
        
        self.middleware['logging'] = LoggingMiddleware(self)
        self.middleware['rate_limit'] = RateLimitMiddleware(self)
    
    def register_middleware(self, middleware: FlowMiddleware):
        """Register custom middleware"""
        self.middleware[middleware.name] = middleware
    
    def load_module(self, filepath: str, module_name: str = None) -> bool:
        """Load a flow module"""
        try:
            module = self.parser.parse_file(filepath)
            
            if module_name:
                module.name = module_name
            
            self.modules[module.name] = module
            
            # Initialize module variables
            for var_name, var_def in module.variables.items():
                if var_def.persistent:
                    # Load from persistent storage if available
                    pass
            
            # Set up timers
            self._setup_timers(module)
            
            # Set up event handlers
            self._setup_event_handlers(module)
            
            self.logger.info(f"Loaded module: {module.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading module {filepath}: {e}")
            return False
    
    def _setup_timers(self, module: FlowModule):
        """Set up timer triggers"""
        for flow_name, flow in module.flows.items():
            for trigger in flow.triggers:
                if trigger.type == TriggerType.TIMER:
                    # Parse timer duration
                    duration = self._parse_duration(trigger.pattern)
                    if duration:
                        self.timers[f"{module.name}:{flow_name}:{trigger.pattern}"] = {
                            'duration': duration,
                            'flow': flow,
                            'module': module,
                            'last_run': time.time()
                        }
    
    def _setup_event_handlers(self, module: FlowModule):
        """Set up event handlers"""
        for flow_name, flow in module.flows.items():
            for trigger in flow.triggers:
                if trigger.type == TriggerType.EVENT:
                    event_name = trigger.pattern
                    if event_name not in self.event_handlers:
                        self.event_handlers[event_name] = []
                    
                    self.event_handlers[event_name].append({
                        'flow': flow,
                        'module': module,
                        'trigger': trigger
                    })
    
    async def create_context(self, user_id: str = None, session_id: str = None) -> FlowContext:
        """Create execution context"""
        context = FlowContext()
        context.user_data['id'] = user_id or 'anonymous'
        context.session_data['id'] = session_id or str(int(time.time()))
        context.request_id = f"{context.user_data['id']}:{context.session_data['id']}:{int(time.time())}"
        
        # Load user variables from all modules
        for module in self.modules.values():
            for var_name, var_def in module.variables.items():
                if var_name not in context.variables:
                    context.variables[var_name] = var_def.value
        
        return context
    
    async def process_input(self, user_input: str, context: FlowContext = None) -> List[str]:
        """Process user input and return responses"""
        if context is None:
            context = await self.create_context()
        
        responses = []
        user_input = user_input.strip()
        
        # Find matching flows
        matching_flows = []
        
        for module in self.modules.values():
            for flow_name, flow in module.flows.items():
                for trigger in flow.triggers:
                    if await self._match_trigger(user_input, trigger, context):
                        matching_flows.append({
                            'flow': flow,
                            'module': module,
                            'trigger': trigger,
                            'priority': trigger.priority
                        })
        
        # Sort by priority and execute
        matching_flows.sort(key=lambda x: x['priority'], reverse=True)
        
        for match in matching_flows:
            try:
                result = await self._execute_flow(match['flow'], match['module'], context)
                if result:
                    responses.extend(result)
            except Exception as e:
                self.logger.error(f"Error executing flow {match['flow'].name}: {e}")
                responses.append(f"Error: {str(e)}")
        
        return responses
    
    async def _match_trigger(self, user_input: str, trigger: FlowTrigger, context: FlowContext) -> bool:
        """Check if user input matches a trigger"""
        
        # Check conditions first
        if not await self._evaluate_conditions(trigger.conditions, context):
            return False
        
        if trigger.type == TriggerType.USER_SAYS:
            # Enhanced pattern matching
            pattern = trigger.pattern.lower()
            user_input_lower = user_input.lower()
            
            # Exact match
            if user_input_lower == pattern:
                return True
            
            # Fuzzy matching with variables
            pattern_with_vars = self._substitute_variables(pattern, context)
            if user_input_lower == pattern_with_vars.lower():
                return True
            
            # Regex support
            if pattern.startswith('/') and pattern.endswith('/'):
                regex_pattern = pattern[1:-1]
                try:
                    return bool(re.search(regex_pattern, user_input, re.IGNORECASE))
                except re.error:
                    pass
            
            # Contains matching for partial phrases
            if pattern.startswith('*') and pattern.endswith('*'):
                return pattern[1:-1] in user_input_lower
            
            return False
        
        elif trigger.type == TriggerType.VARIABLE_EQUALS:
            var_name = trigger.pattern
            expected_value = trigger.conditions[0]['value'] if trigger.conditions else None
            return context.variables.get(var_name) == expected_value
        
        elif trigger.type == TriggerType.ALWAYS:
            return True
        
        return False
    
    async def _execute_flow(self, flow: Flow, module: FlowModule, context: FlowContext) -> List[str]:
        """Execute a flow with middleware support"""
        responses = []
        
        try:
            # Execute middleware stack (before)
            for middleware_name in flow.middleware:
                if middleware_name in self.middleware:
                    middleware = self.middleware[middleware_name]
                    if not await middleware.before_flow(context, flow):
                        self.logger.info(f"Flow {flow.name} stopped by middleware {middleware_name}")
                        return responses
            
            # Execute flow actions
            for action in flow.actions:
                result = await self._execute_action(action, module, context)
                if result:
                    responses.append(result)
            
            # Execute middleware stack (after)
            for middleware_name in reversed(flow.middleware):
                if middleware_name in self.middleware:
                    middleware = self.middleware[middleware_name]
                    responses = await middleware.after_flow(context, flow, responses)
            
            return responses
            
        except Exception as e:
            # Handle errors through middleware
            handled = False
            for middleware_name in flow.middleware:
                if middleware_name in self.middleware:
                    middleware = self.middleware[middleware_name]
                    if await middleware.on_error(context, e):
                        handled = True
                        break
            
            if not handled:
                raise e
    
    async def _execute_action(self, action: FlowAction, module: FlowModule, context: FlowContext) -> Optional[str]:
        """Execute a single action"""
        
        # Check action conditions
        if not await self._evaluate_conditions(action.conditions, context):
            return None
        
        if action.type == ActionType.SAY:
            message = action.params['message']
            # Substitute variables in message
            message = self._substitute_variables(message, context)
            return message
        
        elif action.type == ActionType.SET:
            var_name = action.params['variable']
            value = action.params['value']
            
            # Evaluate value if it's an expression
            if isinstance(value, str) and value in context.variables:
                value = context.variables[value]
            elif isinstance(value, str) and '+' in value:
                # Simple arithmetic evaluation
                try:
                    # Replace variable names with values
                    expr = value
                    for var, val in context.variables.items():
                        if isinstance(val, (int, float)):
                            expr = expr.replace(var, str(val))
                    value = eval(expr)  # Note: In production, use a safer evaluator
                except:
                    pass
            
            context.variables[var_name] = value
            return None
        
        elif action.type == ActionType.CALL:
            func_name = action.params['function']
            params = action.params.get('params', '')
            
            if func_name in module.functions:
                return await self._call_function(module.functions[func_name], module, context, params)
            else:
                self.logger.warning(f"Function {func_name} not found")
                return None
        
        elif action.type == ActionType.API:
            return await self._execute_api_call(action, context)
        
        elif action.type == ActionType.EMIT:
            await self._emit_event(action.params['event'], action.params.get('data'), context)
            return None
        
        elif action.type == ActionType.WAIT:
            duration = self._parse_duration(action.params['duration'])
            if duration:
                await asyncio.sleep(duration)
            return None
        
        elif action.type == ActionType.IF:
            condition = action.params['condition']
            action_str = action.params['action']
            
            # Parse and evaluate condition
            if await self._evaluate_condition_string(condition, context):
                # Parse and execute the action
                nested_action = self.parser._parse_action(action_str)
                if nested_action:
                    return await self._execute_action(nested_action, module, context)
            return None
        
        elif action.type == ActionType.LOOP:
            count = action.params['count']
            action_str = action.params['action']
            responses = []
            
            for i in range(count):
                context.variables['loop_index'] = i
                nested_action = self.parser._parse_action(action_str)
                if nested_action:
                    result = await self._execute_action(nested_action, module, context)
                    if result:
                        responses.append(result)
            
            return '\n'.join(responses) if responses else None
        
        return None
    
    async def _call_function(self, function: FlowFunction, module: FlowModule, context: FlowContext, params: str = '') -> Optional[str]:
        """Call a function"""
        responses = []
        
        # Parse parameters
        if params:
            # Simple parameter parsing - can be enhanced
            param_values = [p.strip().strip('"') for p in params.split(',')]
            for i, param_name in enumerate(function.params):
                if i < len(param_values):
                    context.variables[param_name] = param_values[i]
        
        # Execute function actions
        for action in function.actions:
            result = await self._execute_action(action, module, context)
            if result:
                responses.append(result)
        
        return '\n'.join(responses) if responses else None
    
    async def _execute_api_call(self, action: FlowAction, context: FlowContext) -> Optional[str]:
        """Execute API call"""
        method = action.params['method'].upper()
        url = action.params['url']
        data = action.params.get('data', '')
        
        # Substitute variables in URL and data
        url = self._substitute_variables(url, context)
        
        try:
            if method == 'GET':
                response = requests.get(url, timeout=self.config.get('api_timeout', 10))
            elif method == 'POST':
                json_data = json.loads(data) if data else {}
                response = requests.post(url, json=json_data, timeout=self.config.get('api_timeout', 10))
            else:
                self.logger.warning(f"Unsupported HTTP method: {method}")
                return None
            
            response.raise_for_status()
            
            # Store response for later use
            context.api_responses[url] = response.json() if response.content else {}
            
            return f"API call successful: {response.status_code}"
            
        except Exception as e:
            self.logger.error(f"API call failed: {e}")
            return f"API call failed: {str(e)}"
    
    async def _emit_event(self, event_name: str, data: Any, context: FlowContext):
        """Emit an event"""
        if event_name in self.event_handlers:
            for handler in self.event_handlers[event_name]:
                try:
                    # Add event data to context
                    context.variables[f'event_{event_name}_data'] = data
                    await self._execute_flow(handler['flow'], handler['module'], context)
                except Exception as e:
                    self.logger.error(f"Error in event handler for {event_name}: {e}")
    
    async def _evaluate_conditions(self, conditions: List[Dict[str, Any]], context: FlowContext) -> bool:
        """Evaluate a list of conditions"""
        if not conditions:
            return True
        
        for condition in conditions:
            if not await self._evaluate_single_condition(condition, context):
                return False
        
        return True
    
    async def _evaluate_single_condition(self, condition: Dict[str, Any], context: FlowContext) -> bool:
        """Evaluate a single condition"""
        cond_type = condition['type']
        variable = condition['variable']
        expected_value = condition['value']
        
        actual_value = context.variables.get(variable, '')
        
        if cond_type == 'equals':
            return str(actual_value) == str(expected_value)
        elif cond_type == 'contains':
            return str(expected_value) in str(actual_value)
        elif cond_type == 'greater_than':
            try:
                return float(actual_value) > float(expected_value)
            except:
                return False
        elif cond_type == 'less_than':
            try:
                return float(actual_value) < float(expected_value)
            except:
                return False
        
        return True
    
    async def _evaluate_condition_string(self, condition_str: str, context: FlowContext) -> bool:
        """Evaluate a condition string"""
        # Simple condition evaluation - can be enhanced with a proper parser
        condition_str = self._substitute_variables(condition_str, context)
        
        # Handle basic comparisons
        if ' equals ' in condition_str:
            left, right = condition_str.split(' equals ', 1)
            return left.strip().strip('"') == right.strip().strip('"')
        elif ' contains ' in condition_str:
            left, right = condition_str.split(' contains ', 1)
            return right.strip().strip('"') in left.strip().strip('"')
        
        return True
    
    def _substitute_variables(self, text: str, context: FlowContext) -> str:
        """Substitute variables in text using {variable_name} syntax"""
        for var_name, value in context.variables.items():
            placeholder = f'{{{var_name}}}'
            if placeholder in text:
                text = text.replace(placeholder, str(value))
        
        return text
    
    def _parse_duration(self, duration_str: str) -> Optional[float]:
        """Parse duration string to seconds"""
        duration_str = duration_str.strip()
        
        if duration_str.endswith('s'):
            return float(duration_str[:-1])
        elif duration_str.endswith('m'):
            return float(duration_str[:-1]) * 60
        elif duration_str.endswith('h'):
            return float(duration_str[:-1]) * 3600
        elif duration_str.isdigit():
            return float(duration_str)
        
        return None
    
    async def run_timers(self):
        """Run timer-based triggers"""
        current_time = time.time()
        
        for timer_id, timer_info in self.timers.items():
            if current_time - timer_info['last_run'] >= timer_info['duration']:
                try:
                    context = await self.create_context()
                    await self._execute_flow(timer_info['flow'], timer_info['module'], context)
                    timer_info['last_run'] = current_time
                except Exception as e:
                    self.logger.error(f"Error in timer {timer_id}: {e}")
    
    async def start_background_tasks(self):
        """Start background tasks like timers"""
        self.running = True
        
        while self.running:
            await self.run_timers()
            await asyncio.sleep(1)  # Check every second
    
    def stop(self):
        """Stop the engine"""
        self.running = False
    
    def get_module_info(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a loaded module"""
        if module_name in self.modules:
            module = self.modules[module_name]
            return {
                'name': module.name,
                'flows': list(module.flows.keys()),
                'functions': list(module.functions.keys()),
                'variables': list(module.variables.keys()),
                'imports': module.imports,
                'config': module.config
            }
        return None
    
    def list_modules(self) -> List[str]:
        """List all loaded modules"""
        return list(self.modules.keys())


async def main():
    """Test the enhanced engine"""
    engine = BaikonEngine({
        'log_level': 'INFO',
        'api_timeout': 10,
        'rate_limit': 60
    })
    
    # Create test module content
    test_content = """
version: 2.0

var user_name: string = "Guest"
var mood: string = "neutral"

flow assistant:
    when user says "hello" -> call greet_user
    when user says "/help/" -> call show_help
    when user says "*weather*" -> call get_weather
    when var mood equals "happy" -> call celebrate
    
function greet_user:
    set user_name = "Friend"
    say "Hello {user_name}! How are you feeling today?"
    set mood = "happy"
    
function show_help:
    say "I can help with greetings and weather!"
    
function get_weather:
    say "The weather is sunny today!"
    
function celebrate:
    say "Great to see you're happy, {user_name}!"
"""
    
    # Parse and load module
    module = engine.parser.parse_content(test_content, "test_module")
    engine.modules["test"] = module
    
    # Test inputs
    test_inputs = [
        "hello",
        "help me please", 
        "what's the weather like?",
        "goodbye"
    ]
    
    for user_input in test_inputs:
        print(f"\n--- User: {user_input} ---")
        context = await engine.create_context("test_user", "session_123")
        responses = await engine.process_input(user_input, context)
        
        for response in responses:
            print(f"Bot: {response}")
        
        print(f"Variables: {context.variables}")


if __name__ == "__main__":
    asyncio.run(main())