"""
Baikon Parser - Simple but working version
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class ActionType(Enum):
    SAY = "say"
    SET = "set"
    CALL = "call"


class TriggerType(Enum):
    USER_SAYS = "user_says"


@dataclass
class FlowVariable:
    name: str
    value: Any = None
    type: str = "string"


@dataclass
class FlowAction:
    type: ActionType
    params: Dict[str, Any]


@dataclass
class FlowTrigger:
    type: TriggerType
    pattern: str
    priority: int = 0


@dataclass
class FlowFunction:
    name: str
    actions: List[FlowAction]


@dataclass
class Flow:
    name: str
    triggers: List[FlowTrigger]
    middleware: List[str] = None


@dataclass
class FlowModule:
    name: str
    flows: Dict[str, Flow]
    functions: Dict[str, FlowFunction]
    variables: Dict[str, FlowVariable]
    imports: List[str] = None
    config: Dict[str, Any] = None


class BaikonParser:
    def __init__(self):
        self.flows = {}
        self.functions = {}
        self.variables = {}
    
    def parse_file(self, filepath: str) -> FlowModule:
        """Parse a .flow file and return structured data"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.parse_content(content, filepath)
        except FileNotFoundError:
            raise FileNotFoundError(f"Flow file not found: {filepath}")
        except Exception as e:
            raise Exception(f"Error parsing flow file: {str(e)}")
    
    def parse_content(self, content: str, filename: str = "inline") -> FlowModule:
        """Parse flow content string into structured data"""
        self.flows = {}
        self.functions = {}
        self.variables = {}
        
        # Clean up content
        lines = [line.strip() for line in content.split('\n') if line.strip() and not line.strip().startswith('#')]
        
        current_block = None
        current_name = None
        current_content = []
        
        for line in lines:
            # Skip version and config lines for now
            if line.startswith(('version:', 'config:', 'var ', 'import ')):
                continue
                
            if line.startswith('flow '):
                # Save previous block
                if current_block and current_name:
                    self._process_block(current_block, current_name, current_content)
                
                # Start new flow block
                current_block = 'flow'
                current_name = line[5:].strip(':')
                current_content = []
                
            elif line.startswith('function '):
                # Save previous block
                if current_block and current_name:
                    self._process_block(current_block, current_name, current_content)
                
                # Start new function block
                current_block = 'function'
                current_name = line[9:].strip(':')
                current_content = []
                
            else:
                # Add to current block
                if current_block:
                    current_content.append(line)
        
        # Process final block
        if current_block and current_name:
            self._process_block(current_block, current_name, current_content)
        
        # Set default variables
        self.variables = {
            'user_name': FlowVariable('user_name', 'Friend'),
            'conversation_count': FlowVariable('conversation_count', 0),
            'user_mood': FlowVariable('user_mood', 'neutral'),
            'last_topic': FlowVariable('last_topic', 'none'),
            'user_preferences': FlowVariable('user_preferences', {})
        }
        
        return FlowModule(
            name=filename,
            flows=self.flows,
            functions=self.functions,
            variables=self.variables,
            imports=[],
            config={}
        )
    
    def _process_block(self, block_type: str, name: str, content: List[str]):
        """Process a parsed block"""
        if block_type == 'flow':
            self.flows[name] = self._parse_flow_triggers(content, name)
        elif block_type == 'function':
            self.functions[name] = self._parse_function_actions(content, name)
    
    def _parse_flow_triggers(self, content: List[str], flow_name: str) -> Flow:
        """Parse flow trigger rules"""
        triggers = []
        
        for line in content:
            # Skip middleware lines for now
            if line.startswith('use '):
                continue
                
            # Match pattern: when user says "text" -> call function_name
            match = re.match(r'when user says "([^"]+)"\s*->\s*call\s+(\w+)', line)
            if match:
                trigger_text = match.group(1)
                function_name = match.group(2)
                triggers.append(FlowTrigger(
                    type=TriggerType.USER_SAYS,
                    pattern=trigger_text
                ))
                # Store the function call info
                if flow_name not in self._trigger_actions:
                    self._trigger_actions = {}
                if flow_name not in self._trigger_actions:
                    self._trigger_actions[flow_name] = {}
                self._trigger_actions[flow_name][trigger_text] = function_name
        
        return Flow(name=flow_name, triggers=triggers, middleware=[])
    
    def _parse_function_actions(self, content: List[str], func_name: str) -> FlowFunction:
        """Parse function action commands"""
        actions = []
        
        for line in content:
            # Match pattern: say "text"
            match = re.match(r'say "([^"]+)"', line)
            if match:
                message = match.group(1)
                actions.append(FlowAction(
                    type=ActionType.SAY,
                    params={"message": message}
                ))
            
            # Match pattern: set variable = value
            match = re.match(r'set (\w+)\s*=\s*(.+)', line)
            if match:
                var_name = match.group(1)
                value = match.group(2).strip().strip('"')
                actions.append(FlowAction(
                    type=ActionType.SET,
                    params={"variable": var_name, "value": value}
                ))
        
        return FlowFunction(name=func_name, actions=actions)
    
    # Store trigger->function mapping
    _trigger_actions = {}
    
    def get_function_for_trigger(self, flow_name: str, trigger_pattern: str) -> Optional[str]:
        """Get function name for a trigger pattern"""
        return self._trigger_actions.get(flow_name, {}).get(trigger_pattern)


def main():
    """Test the parser"""
    parser = BaikonParser()
    
    sample_content = """
flow assistant:
    when user says "hello" -> call greet_user
    when user says "help" -> call show_help

function greet_user:
    say "Hi there! I'm your assistant."

function show_help:
    say "I can help you with various tasks."
"""
    
    try:
        result = parser.parse_content(sample_content)
        print("✅ Parser working!")
        print(f"Flows: {list(result.flows.keys())}")
        print(f"Functions: {list(result.functions.keys())}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()