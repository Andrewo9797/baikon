"""
Baikon CLI v2.0 - Enhanced command-line interface with async support,
real-time features, and visual flow debugging
"""

import os
import sys
import asyncio
import json
import time
from typing import Optional, Dict, Any
from engine import BaikonEngine, FlowContext
from parser import FlowModule


class BaikonCLI:
    def __init__(self):
        self.engine = BaikonEngine()
        self.running = False
        self.current_module = None
        self.current_context = None
        self.auto_save = True
        self.session_history = []
        
    async def start(self, flow_file: str = "main.flow", debug: bool = False, config: Dict[str, Any] = None):
        """Start the enhanced CLI"""
        
        # Apply configuration
        if config:
            self.engine.config.update(config)
        
        self.engine.logger.setLevel('DEBUG' if debug else 'INFO')
        
        print("🚀 Baikon CLI v2.0 - Enhanced AI Agent Framework")
        print("=" * 60)
        
        # Load the flow file
        if not os.path.exists(flow_file):
            print(f"❌ Flow file '{flow_file}' not found!")
            
            # Offer to create a sample file
            if await self._prompt_create_sample(flow_file):
                await self._create_sample_flow(flow_file)
            else:
                return
        
        if not self.engine.load_module(flow_file, "main"):
            print(f"❌ Failed to load flow file '{flow_file}'")
            return
        
        self.current_module = self.engine.modules["main"]
        print(f"✅ Loaded module: {flow_file}")
        
        # Create session context
        self.current_context = await self.engine.create_context("cli_user", f"session_{int(time.time())}")
        
        # Show module information
        await self._show_module_info()
        
        # Start background tasks
        asyncio.create_task(self.engine.start_background_tasks())
        
        print("\n💬 Start chatting! Type 'help' for commands or 'quit' to exit.")
        print("-" * 60)
        
        self.running = True
        await self._main_loop()
    
    async def _prompt_create_sample(self, filename: str) -> bool:
        """Ask user if they want to create a sample flow file"""
        try:
            response = input(f"Would you like to create a sample flow file '{filename}'? (y/n): ").strip().lower()
            return response in ['y', 'yes']
        except (KeyboardInterrupt, EOFError):
            return False
    
    async def _create_sample_flow(self, filename: str):
        """Create a sample flow file"""
        sample_content = """version: 2.0

# Define variables
var user_name: string = "Friend"
var conversation_count: int = 0
var user_mood: string = "neutral"

# Configuration
config:
    timeout: 30
    log_level: "info"

# Main conversation flow
flow assistant:
    when user says "hello" -> call greet_user
    when user says "hi" -> call greet_user
    when user says "/help/" -> call show_help
    when user says "*weather*" -> call get_weather
    when user says "*joke*" -> call tell_joke
    when user says "bye" -> call say_goodbye
    when user says "*mood*" -> call check_mood
    when var user_mood equals "happy" -> call celebrate

# Admin flow (with conditions)
flow admin:
    when user says "status" if user_name equals "Admin" -> call show_status
    when user says "reset" if user_name equals "Admin" -> call reset_data

# Functions
function greet_user:
    set conversation_count = conversation_count + 1
    say "Hello {user_name}! This is our conversation #{conversation_count}."
    if conversation_count equals "1" then say "Nice to meet you!"
    set user_mood = "friendly"

function show_help:
    say "I can help you with:"
    say "• Greetings (hello, hi)"
    say "• Weather information (ask about weather)"
    say "• Jokes (ask for a joke)"
    say "• Mood tracking (mention your mood)"
    say "• Commands: status, reset (admin only)"

function get_weather:
    say "🌤️ Today looks sunny with a chance of productivity!"
    say "Perfect weather for coding some Baikon!"

function tell_joke:
    say "Why don't programmers like nature?"
    wait 2s
    say "It has too many bugs! 🐛😄"
    set user_mood = "amused"

function say_goodbye:
    say "Goodbye {user_name}! Thanks for {conversation_count} great conversations!"
    say "Hope to see you again soon! 👋"

function check_mood:
    if user_mood equals "happy" then say "I can sense you're in a great mood!"
    if user_mood equals "neutral" then say "How are you feeling today?"
    say "Your current mood: {user_mood}"

function celebrate:
    say "🎉 Wonderful! I love when you're happy!"
    say "Keep that positive energy flowing!"

function show_status:
    say "📊 System Status:"
    say "• User: {user_name}"
    say "• Conversations: {conversation_count}"
    say "• Current mood: {user_mood}"
    say "• Uptime: Good!"

function reset_data:
    set conversation_count = 0
    set user_mood = "neutral"
    say "🔄 Data reset successfully!"
"""
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(sample_content)
            print(f"✅ Created sample flow file: {filename}")
        except Exception as e:
            print(f"❌ Error creating sample file: {e}")
    
    async def _show_module_info(self):
        """Display information about the loaded module"""
        info = self.engine.get_module_info("main")
        if info:
            print(f"📋 Module Overview:")
            print(f"   • Flows: {len(info['flows'])} ({', '.join(info['flows'])})")
            print(f"   • Functions: {len(info['functions'])} ({', '.join(info['functions'])})")
            print(f"   • Variables: {len(info['variables'])} ({', '.join(info['variables'])})")
            
            if info['imports']:
                print(f"   • Imports: {', '.join(info['imports'])}")
    
    async def _main_loop(self):
        """Enhanced main interaction loop"""
        while self.running:
            try:
                # Get user input with rich prompt
                user_input = await self._get_user_input()
                
                if not user_input.strip():
                    continue
                
                # Record in history
                self.session_history.append({
                    'timestamp': time.time(),
                    'type': 'user',
                    'content': user_input
                })
                
                # Handle special commands
                if await self._handle_command(user_input):
                    continue
                
                # Process through engine
                start_time = time.time()
                responses = await self.engine.process_input(user_input, self.current_context)
                processing_time = time.time() - start_time
                
                # Display responses
                if responses:
                    for response in responses:
                        print(f"🤖 {response}")
                        
                        # Record in history
                        self.session_history.append({
                            'timestamp': time.time(),
                            'type': 'bot',
                            'content': response
                        })
                else:
                    print("🤔 I don't understand that. Try 'help' for available commands.")
                
                # Show debug info if enabled
                if self.engine.logger.level <= 10:  # DEBUG level
                    print(f"⚡ Processed in {processing_time:.3f}s")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except EOFError:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                if self.engine.logger.level <= 10:
                    import traceback
                    traceback.print_exc()
        
        # Cleanup
        self.engine.stop()
        
        if self.auto_save:
            await self._save_session()
    
    async def _get_user_input(self) -> str:
        """Get user input with enhanced prompt"""
        try:
            # Show current context info in debug mode
            if self.engine.logger.level <= 10 and self.current_context:
                mood = self.current_context.variables.get('user_mood', 'unknown')
                name = self.current_context.variables.get('user_name', 'User')
                prompt = f"{name} ({mood}) → "
            else:
                prompt = "You → "
            
            # Use asyncio for non-blocking input (in a real async app, you'd use aiohttp or similar)
            return input(prompt)
            
        except (KeyboardInterrupt, EOFError):
            raise
    
    async def _handle_command(self, user_input: str) -> bool:
        """Handle special CLI commands"""
        command = user_input.lower().strip()
        
        # Basic commands
        if command in ['quit', 'exit', 'q']:
            print("👋 Thanks for using FlowLang!")
            self.running = False
            return True
        
        elif command == 'help':
            await self._show_help()
            return True
        
        elif command == 'debug':
            current_level = self.engine.logger.level
            new_level = 20 if current_level <= 10 else 10  # Toggle between INFO and DEBUG
            self.engine.logger.setLevel(new_level)
            mode = "ON" if new_level <= 10 else "OFF"
            print(f"🔧 Debug mode: {mode}")
            return True
        
        elif command == 'reload':
            await self._reload_module()
            return True
        
        elif command == 'variables' or command == 'vars':
            await self._show_variables()
            return True
        
        elif command == 'history':
            await self._show_history()
            return True
        
        elif command == 'clear':
            os.system('cls' if os.name == 'nt' else 'clear')
            print("🚀 Baikon CLI v2.0")
            return True
        
        elif command == 'save':
            await self._save_session()
            return True
        
        elif command == 'status':
            await self._show_status()
            return True
        
        elif command.startswith('set '):
            await self._handle_set_command(command)
            return True
        
        elif command == 'flows':
            await self._show_flows()
            return True
        
        elif command == 'functions':
            await self._show_functions()
            return True
        
        elif command.startswith('call '):
            await self._handle_call_command(command)
            return True
        
        return False
    
    async def _show_help(self):
        """Display comprehensive help"""
        print("""
🔧 Baikon CLI Commands:
   
📝 Basic Commands:
   help           - Show this help message
   quit/exit      - Exit the CLI
   clear          - Clear the screen
   debug          - Toggle debug mode
   
🔄 Flow Management:
   reload         - Reload the current flow file
   flows          - List available flows
   functions      - List available functions
   status         - Show system status
   
💾 Session & Data:
   variables/vars - Show current variables
   set <var>=<val>- Set a variable value
   history        - Show conversation history
   save           - Save current session
   
🚀 Advanced:
   call <function> - Call a function directly
   
💡 Tips:
   • Use natural language to interact with your flows
   • Variables are remembered throughout the session
   • Check debug mode for detailed execution info
   • All conversations are automatically saved
        """)
    
    async def _reload_module(self):
        """Reload the current module"""
        if self.current_module:
            module_name = self.current_module.name
            print(f"🔄 Reloading module...")
            
            # Find the original file path
            # This would need to be tracked better in a real implementation
            flow_file = f"{module_name}.flow" if not module_name.endswith('.flow') else module_name
            
            if os.path.exists(flow_file):
                if self.engine.load_module(flow_file, "main"):
                    self.current_module = self.engine.modules["main"]
                    # Reset context variables
                    self.current_context = await self.engine.create_context("cli_user", f"session_{int(time.time())}")
                    print("✅ Module reloaded successfully!")
                    await self._show_module_info()
                else:
                    print("❌ Failed to reload module")
            else:
                print(f"❌ Module file not found: {flow_file}")
    
    async def _show_variables(self):
        """Show current context variables"""
        if self.current_context and self.current_context.variables:
            print("📊 Current Variables:")
            for name, value in self.current_context.variables.items():
                value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                print(f"   {name} = {value_str}")
        else:
            print("📊 No variables set")
    
    async def _show_history(self):
        """Show conversation history"""
        if self.session_history:
            print("📚 Conversation History:")
            for i, entry in enumerate(self.session_history[-10:], 1):  # Show last 10
                timestamp = time.strftime("%H:%M:%S", time.localtime(entry['timestamp']))
                icon = "👤" if entry['type'] == 'user' else "🤖"
                print(f"   {i:2d}. [{timestamp}] {icon} {entry['content']}")
        else:
            print("📚 No conversation history")
    
    async def _save_session(self):
        """Save session to file"""
        try:
            session_data = {
                'timestamp': time.time(),
                'variables': self.current_context.variables if self.current_context else {},
                'history': self.session_history,
                'module': self.current_module.name if self.current_module else None
            }
            
            filename = f"session_{int(time.time())}.json"
            with open(filename, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            print(f"💾 Session saved to {filename}")
        except Exception as e:
            print(f"❌ Error saving session: {e}")
    
    async def _show_status(self):
        """Show system status"""
        uptime = time.time() - (self.current_context.start_time if self.current_context else time.time())
        
        print("📊 System Status:")
        print(f"   • Module: {self.current_module.name if self.current_module else 'None'}")
        print(f"   • Session uptime: {uptime:.1f}s")
        print(f"   • Messages exchanged: {len(self.session_history)}")
        print(f"   • Active variables: {len(self.current_context.variables) if self.current_context else 0}")
        print(f"   • Debug mode: {'ON' if self.engine.logger.level <= 10 else 'OFF'}")
        print(f"   • Background tasks: {'Running' if self.engine.running else 'Stopped'}")
    
    async def _handle_set_command(self, command: str):
        """Handle variable setting command"""
        try:
            # Parse: set variable_name = value
            parts = command[4:].split('=', 1)
            if len(parts) == 2:
                var_name = parts[0].strip()
                value = parts[1].strip().strip('"')
                
                # Try to parse as number
                try:
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    pass  # Keep as string
                
                if self.current_context:
                    self.current_context.variables[var_name] = value
                    print(f"✅ Set {var_name} = {value}")
                else:
                    print("❌ No active context")
            else:
                print("❌ Usage: set <variable>=<value>")
        except Exception as e:
            print(f"❌ Error setting variable: {e}")
    
    async def _show_flows(self):
        """Show available flows"""
        if self.current_module:
            print("🔄 Available Flows:")
            for flow_name, flow in self.current_module.flows.items():
                trigger_count = len(flow.triggers)
                print(f"   • {flow_name}: {trigger_count} triggers")
                
                if self.engine.logger.level <= 10:  # Debug mode
                    for trigger in flow.triggers[:2]:  # Show first 2 triggers
                        print(f"     - {trigger.type.value}: {trigger.pattern}")
                    if len(flow.triggers) > 2:
                        print(f"     - ... and {len(flow.triggers) - 2} more")
        else:
            print("❌ No module loaded")
    
    async def _show_functions(self):
        """Show available functions"""
        if self.current_module:
            print("⚙️ Available Functions:")
            for func_name, function in self.current_module.functions.items():
                action_count = len(function.actions)
                params = f"({', '.join(function.params)})" if function.params else "()"
                async_marker = "async " if function.async_ else ""
                print(f"   • {async_marker}{func_name}{params}: {action_count} actions")
        else:
            print("❌ No module loaded")
    
    async def _handle_call_command(self, command: str):
        """Handle direct function calls"""
        try:
            # Parse: call function_name(param1, param2)
            func_call = command[5:].strip()
            
            if '(' in func_call:
                func_name = func_call.split('(')[0]
                params = func_call.split('(')[1].split(')')[0]
            else:
                func_name = func_call
                params = ""
            
            if self.current_module and func_name in self.current_module.functions:
                function = self.current_module.functions[func_name]
                result = await self.engine._call_function(function, self.current_module, self.current_context, params)
                
                if result:
                    print(f"🤖 {result}")
                else:
                    print(f"✅ Function {func_name} executed")
            else:
                print(f"❌ Function '{func_name}' not found")
                
        except Exception as e:
            print(f"❌ Error calling function: {e}")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Baikon CLI v2.0 - Enhanced AI Agent Framework")
    parser.add_argument("file", nargs="?", default="main.flow", 
                       help="Flow file to load (default: main.flow)")
    parser.add_argument("--debug", action="store_true", 
                       help="Enable debug mode")
    parser.add_argument("--config", type=str,
                       help="JSON config file path")
    parser.add_argument("--auto-save", action="store_true", default=True,
                       help="Auto-save sessions (default: True)")
    
    args = parser.parse_args()
    
    # Load configuration
    config = {}
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Warning: Error loading config file: {e}")
    
    cli = BaikonCLI()
    cli.auto_save = args.auto_save
    
    await cli.start(args.file, args.debug, config)


if __name__ == "__main__":
    asyncio.run(main())
