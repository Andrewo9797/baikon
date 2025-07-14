"""
Baikon Parser v2.0 - Enhanced DSL with variables, conditions, and integrations
"""

import re
import json
import yaml
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum


class ActionType(Enum):
    SAY = "say"
    SET = "set"
    GET = "get"
    CALL = "call"
    API = "api"
    IF = "if"
    LOOP = "loop"
    IMPORT = "import"
    EMIT = "emit"
    WAIT = "wait"


class TriggerType(Enum):
    USER_SAYS = "user_says"
    VARIABLE_EQUALS = "variable_equals"
    API_RESPONSE = "api_response"
    TIMER = "timer"
    EVENT = "event"
    ALWAYS = "always"


@dataclass
class FlowVariable:
    name: str
    value: Any = None
    type: str = "string"
    persistent: bool = False


@dataclass
class FlowAction:
    type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)
    conditions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FlowTrigger:
    type: TriggerType
    pattern: str
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    priority: int = 0


@dataclass
class FlowFunction:
    name: str
    actions: List[FlowAction] = field(default_factory=list)
    params: List[str] = field(default_factory=list)
    returns: Optional[str] = None
    async_: bool = False


@dataclass
class FlowModule:
    name: str
    flows: Dict[str, 'Flow'] = field(default_factory=dict)
    functions: Dict[str, FlowFunction] = field(default_factory=dict)
    variables: Dict[str, FlowVariable] = field(default_factory=dict)
    imports: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Flow:
    name: str
    triggers: List[FlowTrigger] = field(default_factory=list)
    actions: List[FlowAction] = field(default_factory=list)
    middleware: List[str] = field(default_factory=list)
    timeout: Optional[int] = None
    retry_count: int = 0


class BaikonParser:
    def __init__(self):
        self.modules = {}
        self.current_module = None
        self.line_number = 0
        self.syntax_version = "2.0"
        
    def parse_file(self, filepath: str) -> FlowModule:
        """Parse a .flow file and return structured module"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.parse_content(content, filepath)
        except FileNotFoundError:
            raise FileNotFoundError(f"Flow file not found: {filepath}")
        except Exception as e:
            raise Exception(f"Error parsing flow file {filepath} at line {self.line_number}: {str(e)}")
    
    def parse_content(self, content: str, filename: str = "inline") -> FlowModule:
        """Parse flow content string into structured module"""
        lines = content.split('\n')
        self.line_number = 0
        
        # Initialize module
        module = FlowModule(name=filename)
        self.current_module = module
        
        # Parse configuration and imports first
        self._parse_header(lines, module)
        
        # Parse main content
        self._parse_blocks(lines, module)
        
        # Validate and resolve references
        self._validate_module(module)
        
        return module
    
    def _parse_header(self, lines: List[str], module: FlowModule):
        """Parse module header (config, imports, variables)"""
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            self.line_number = i + 1
            
            if not line or line.startswith('#'):
                i += 1
                continue
                
            # Parse version
            if line.startswith('version:'):
                module.config['version'] = line.split(':', 1)[1].strip()
                
            # Parse imports
            elif line.startswith('import '):
                imports = line[7:].strip().split(',')
                module.imports.extend([imp.strip() for imp in imports])
                
            # Parse global variables
            elif line.startswith('var '):
                var_def = line[4:].strip()
                self._parse_variable(var_def, module)
                
            # Parse configuration
            elif line.startswith('config:'):
                i = self._parse_config_block(lines, i + 1, module)
                continue
                
            # Stop at first non-header line
            elif line.startswith(('flow ', 'function ', 'middleware ')):
                break
                
            i += 1
    
    def _parse_blocks(self, lines: List[str], module: FlowModule):
        """Parse main content blocks"""
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            self.line_number = i + 1
            
            if not line or line.startswith('#'):
                i += 1
                continue
                
            # Parse flows
            if line.startswith('flow '):
                flow_name = line[5:].strip(':')
                flow = Flow(name=flow_name)
                i = self._parse_flow_block(lines, i + 1, flow)
                module.flows[flow_name] = flow
                
            # Parse functions
            elif line.startswith('function '):
                func_def = line[9:].strip(':')
                func = self._parse_function_signature(func_def)
                i = self._parse_function_block(lines, i + 1, func)
                module.functions[func.name] = func
                
            # Parse middleware
            elif line.startswith('middleware '):
                middleware_name = line[11:].strip(':')
                middleware = FlowFunction(name=middleware_name)
                i = self._parse_function_block(lines, i + 1, middleware)
                module.functions[f"middleware:{middleware_name}"] = middleware
                
            else:
                i += 1
    
    def _parse_flow_block(self, lines: List[str], start_idx: int, flow: Flow) -> int:
        """Parse a flow block and return next line index"""
        i = start_idx
        
        while i < len(lines):
            line = lines[i].strip()
            self.line_number = i + 1
            
            if not line or line.startswith('#'):
                i += 1
                continue
                
            # End of block
            if not line.startswith((' ', '\t')) and line.endswith(':'):
                break
                
            # Parse triggers
            if line.startswith('when '):
                trigger = self._parse_trigger(line)
                flow.triggers.append(trigger)
                
            # Parse direct actions
            elif line.startswith(('say ', 'set ', 'call ', 'api ', 'emit ')):
                action = self._parse_action(line)
                flow.actions.append(action)
                
            # Parse middleware
            elif line.startswith('use '):
                middleware_name = line[4:].strip()
                flow.middleware.append(middleware_name)
                
            # Parse flow config
            elif line.startswith('timeout:'):
                flow.timeout = int(line.split(':', 1)[1].strip())
                
            elif line.startswith('retry:'):
                flow.retry_count = int(line.split(':', 1)[1].strip())
                
            i += 1
            
        return i
    
    def _parse_function_block(self, lines: List[str], start_idx: int, func: FlowFunction) -> int:
        """Parse a function block and return next line index"""
        i = start_idx
        
        while i < len(lines):
            line = lines[i].strip()
            self.line_number = i + 1
            
            if not line or line.startswith('#'):
                i += 1
                continue
                
            # End of block
            if not line.startswith((' ', '\t')) and line.endswith(':'):
                break
                
            # Parse actions
            action = self._parse_action(line)
            if action:
                func.actions.append(action)
                
            i += 1
            
        return i
    
    def _parse_trigger(self, line: str) -> FlowTrigger:
        """Parse a trigger line"""
        # when user says "hello" -> call greet_user
        # when var user_mood equals "happy" -> call celebrate
        # when api weather returns -> call process_weather
        # when timer 5s -> call timeout_handler
        # when event user_login -> call welcome_user
        
        patterns = [
            (r'when user says "([^"]+)"(?:\s+if\s+(.+?))?\s*->\s*call\s+(\w+)', TriggerType.USER_SAYS),
            (r'when var (\w+) equals "([^"]+)"(?:\s+if\s+(.+?))?\s*->\s*call\s+(\w+)', TriggerType.VARIABLE_EQUALS),
            (r'when api (\w+) returns(?:\s+if\s+(.+?))?\s*->\s*call\s+(\w+)', TriggerType.API_RESPONSE),
            (r'when timer (\d+[smh]?)(?:\s+if\s+(.+?))?\s*->\s*call\s+(\w+)', TriggerType.TIMER),
            (r'when event (\w+)(?:\s+if\s+(.+?))?\s*->\s*call\s+(\w+)', TriggerType.EVENT),
            (r'when always(?:\s+if\s+(.+?))?\s*->\s*call\s+(\w+)', TriggerType.ALWAYS),
        ]
        
        for pattern, trigger_type in patterns:
            match = re.match(pattern, line)
            if match:
                groups = match.groups()
                trigger = FlowTrigger(
                    type=trigger_type,
                    pattern=groups[0] if groups[0] else "",
                    conditions=self._parse_conditions(groups[-2] if len(groups) > 2 and groups[-2] else "")
                )
                return trigger
        
        raise ValueError(f"Invalid trigger syntax: {line}")
    
    def _parse_action(self, line: str) -> Optional[FlowAction]:
        """Parse an action line"""
        # say "Hello world"
        # set user_name = "John"
        # get weather from api
        # call process_data(user_input)
        # api get https://api.weather.com/current
        # if user_mood equals "happy" then say "Great!"
        # loop 3 times: call send_reminder
        # emit user_login_event
        # wait 5s
        
        action_patterns = [
            (r'say "([^"]+)"(?:\s+if\s+(.+))?', ActionType.SAY, lambda m: {"message": m.group(1)}),
            (r'set (\w+)\s*=\s*"([^"]+)"(?:\s+if\s+(.+))?', ActionType.SET, lambda m: {"variable": m.group(1), "value": m.group(2)}),
            (r'set (\w+)\s*=\s*(\w+)(?:\s+if\s+(.+))?', ActionType.SET, lambda m: {"variable": m.group(1), "value": m.group(2)}),
            (r'call (\w+)(?:\(([^)]*)\))?(?:\s+if\s+(.+))?', ActionType.CALL, lambda m: {"function": m.group(1), "params": m.group(2) or ""}),
            (r'api (get|post|put|delete)\s+([^\s]+)(?:\s+with\s+(.+))?(?:\s+if\s+(.+))?', ActionType.API, 
             lambda m: {"method": m.group(1), "url": m.group(2), "data": m.group(3) or ""}),
            (r'emit (\w+)(?:\s+with\s+(.+))?(?:\s+if\s+(.+))?', ActionType.EMIT, lambda m: {"event": m.group(1), "data": m.group(2) or ""}),
            (r'wait (\d+[smh]?)(?:\s+if\s+(.+))?', ActionType.WAIT, lambda m: {"duration": m.group(1)}),
            (r'if (.+?) then (.+)', ActionType.IF, lambda m: {"condition": m.group(1), "action": m.group(2)}),
            (r'loop (\d+) times:\s*(.+)', ActionType.LOOP, lambda m: {"count": int(m.group(1)), "action": m.group(2)}),
        ]
        
        for pattern, action_type, param_func in action_patterns:
            match = re.match(pattern, line)
            if match:
                params = param_func(match)
                conditions = []
                
                # Extract conditions from the last group if present
                groups = match.groups()
                if groups and groups[-1]:
                    conditions = self._parse_conditions(groups[-1])
                
                return FlowAction(
                    type=action_type,
                    params=params,
                    conditions=conditions
                )
        
        return None
    
    def _parse_conditions(self, condition_str: str) -> List[Dict[str, Any]]:
        """Parse condition expressions"""
        if not condition_str:
            return []
        
        # Simple condition parsing - can be enhanced
        conditions = []
        for cond in condition_str.split(' and '):
            cond = cond.strip()
            if ' equals ' in cond:
                var, value = cond.split(' equals ', 1)
                conditions.append({
                    "type": "equals",
                    "variable": var.strip(),
                    "value": value.strip().strip('"')
                })
            elif ' contains ' in cond:
                var, value = cond.split(' contains ', 1)
                conditions.append({
                    "type": "contains",
                    "variable": var.strip(),
                    "value": value.strip().strip('"')
                })
        
        return conditions
    
    def _parse_variable(self, var_def: str, module: FlowModule):
        """Parse variable definition"""
        # var user_name: string = "default"
        # var counter: int = 0
        # var persistent settings: json = {}
        
        parts = var_def.split('=')
        var_info = parts[0].strip()
        default_value = parts[1].strip().strip('"') if len(parts) > 1 else None
        
        persistent = 'persistent' in var_info
        if persistent:
            var_info = var_info.replace('persistent', '').strip()
        
        if ':' in var_info:
            name, var_type = var_info.split(':', 1)
            name = name.strip()
            var_type = var_type.strip()
        else:
            name = var_info.strip()
            var_type = "string"
        
        module.variables[name] = FlowVariable(
            name=name,
            value=default_value,
            type=var_type,
            persistent=persistent
        )
    
    def _parse_function_signature(self, func_def: str) -> FlowFunction:
        """Parse function signature"""
        # process_data(input: string) -> string
        # send_email(to: string, subject: string)
        # async fetch_data() -> json
        
        async_ = func_def.startswith('async ')
        if async_:
            func_def = func_def[6:]
        
        returns = None
        if ' -> ' in func_def:
            func_def, returns = func_def.split(' -> ', 1)
            returns = returns.strip()
        
        if '(' in func_def:
            name = func_def.split('(')[0].strip()
            params_str = func_def.split('(')[1].split(')')[0]
            params = [p.strip().split(':')[0] for p in params_str.split(',') if p.strip()]
        else:
            name = func_def.strip()
            params = []
        
        return FlowFunction(
            name=name,
            params=params,
            returns=returns,
            async_=async_
        )
    
    def _parse_config_block(self, lines: List[str], start_idx: int, module: FlowModule) -> int:
        """Parse configuration block"""
        i = start_idx
        
        while i < len(lines):
            line = lines[i].strip()
            self.line_number = i + 1
            
            if not line or line.startswith('#'):
                i += 1
                continue
                
            if not line.startswith((' ', '\t')):
                break
            
            # Parse key-value pairs
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # Try to parse as JSON/YAML
                try:
                    if value.startswith(('{', '[', '"')):
                        value = json.loads(value)
                    elif value.lower() in ('true', 'false'):
                        value = value.lower() == 'true'
                    elif value.isdigit():
                        value = int(value)
                except:
                    pass  # Keep as string
                
                module.config[key] = value
            
            i += 1
        
        return i
    
    def _validate_module(self, module: FlowModule):
        """Validate module structure and references"""
        errors = []
        
        # Check function references
        for flow in module.flows.values():
            for trigger in flow.triggers:
                # Extract function calls from trigger actions
                pass  # TODO: Implement validation
        
        # Check variable references
        # Check import validity
        # Check syntax consistency
        
        if errors:
            raise ValueError(f"Module validation errors: {errors}")
    
    def export_to_json(self, module: FlowModule) -> str:
        """Export module to JSON format"""
        def serialize_obj(obj):
            if hasattr(obj, '__dict__'):
                return {k: serialize_obj(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, list):
                return [serialize_obj(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: serialize_obj(v) for k, v in obj.items()}
            elif isinstance(obj, Enum):
                return obj.value
            else:
                return obj
        
        return json.dumps(serialize_obj(module), indent=2)
    
    def export_to_yaml(self, module: FlowModule) -> str:
        """Export module to YAML format"""
        data = json.loads(self.export_to_json(module))
        return yaml.dump(data, default_flow_style=False)


def main():
    """Test the enhanced parser"""
    parser = BaikonParser()
    
    # Test with enhanced syntax
    sample_content = """
version: 2.0
import auth, database, weather_api

var user_name: string = "Guest"
var login_count: int = 0
var persistent user_preferences: json = {}

config:
    timeout: 30
    retry_attempts: 3
    log_level: "info"

middleware auth_check:
    if user_name equals "Guest" then call require_login

flow assistant:
    use auth_check
    when user says "hello" -> call greet_user
    when user says "weather" -> call get_weather
    when var user_mood equals "sad" -> call cheer_up
    when timer 5m -> call check_reminders
    timeout: 60

flow admin:
    when user says "status" if user_role equals "admin" -> call show_status
    when event system_alert -> call handle_alert

function greet_user:
    set login_count = login_count + 1
    say "Hello {user_name}! You've logged in {login_count} times."
    emit user_greeted with user_name

async function get_weather:
    api get https://api.weather.com/current
    if api_response contains "rain" then say "Don't forget your umbrella!"
    wait 2s
    say "Weather updated!"

function cheer_up:
    say "I hope your day gets better!"
    set user_mood = "neutral"

function check_reminders:
    loop 3 times: call send_reminder
    emit reminders_sent
"""
    
    try:
        module = parser.parse_content(sample_content)
        print("✅ Enhanced Baikon parsed successfully!")
        print(f"📊 Module: {module.name}")
        print(f"   Flows: {len(module.flows)}")
        print(f"   Functions: {len(module.functions)}")
        print(f"   Variables: {len(module.variables)}")
        print(f"   Imports: {len(module.imports)}")
        
        # Export examples
        print("\n📄 JSON Export:")
        print(parser.export_to_json(module)[:500] + "...")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
