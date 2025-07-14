"""
Baikon CLI - Simple but working version
"""

import os
import sys
import asyncio
import time
from typing import Optional
from engine import BaikonEngine, FlowContext


class BaikonCLI:
    def __init__(self):
        self.engine = BaikonEngine()
        self.running = False
        self.current_context = None
    
    async def start(self, flow_file: str = "main.flow", debug: bool = False):
        """Start the CLI"""
        print("🚀 Baikon CLI v2.0 - Enhanced AI Agent Framework")
        print("=" * 60)
        
        # Load the flow file
        if not os.path.exists(flow_file):
            print(f"❌ Flow file '{flow_file}' not found!")
            return
        
        if not self.engine.load_module(flow_file, "main"):
            print(f"❌ Failed to load flow file '{flow_file}'")
            return
        
        print(f"✅ Loaded module: {flow_file}")
        
        # Create context
        self.current_context = await self.engine.create_context("cli_user", f"session_{int(time.time())}")
        
        # Show module info
        await self._show_module_info()
        
        print("\n💬 Start chatting! Type 'help' for commands or 'quit' to exit.")
        print("-" * 60)
        
        self.running = True
        await self._main_loop()
    
    async def _show_module_info(self):
        """Display module information"""
        info = self.engine.get_module_info("main")
        if info:
            print(f"📋 Module Overview:")
            print(f"   • Flows: {len(info['flows'])} ({', '.join(info['flows'])})")
            print(f"   • Functions: {len(info['functions'])} ({', '.join(info['functions'])})")
            print(f"   • Variables: {len(info['variables'])} ({', '.join(info['variables'])})")
    
    async def _main_loop(self):
        """Main interaction loop"""
        while self.running:
            try:
                user_input = input("You → ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if await self._handle_command(user_input):
                    continue
                
                # Process through engine
                responses = await self.engine.process_input(user_input, self.current_context)
                
                if responses:
                    for response in responses:
                        print(f"🤖 {response}")
                else:
                    print("🤔 I don't understand that. Try 'help' for available commands.")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except EOFError:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    async def _handle_command(self, user_input: str) -> bool:
        """Handle special commands"""
        command = user_input.lower()
        
        if command in ['quit', 'exit', 'q']:
            print("👋 Thanks for using Baikon!")
            self.running = False
            return True
        
        elif command == 'help':
            self._show_help()
            return True
        
        elif command == 'variables' or command == 'vars':
            self._show_variables()
            return True
        
        elif command == 'flows':
            self._show_flows()
            return True
        
        elif command == 'functions':
            self._show_functions()
            return True
        
        elif command.startswith('call '):
            await self._handle_call_command(command)
            return True
        
        elif command.startswith('set '):
            self._handle_set_command(command)
            return True
        
        return False
    
    def _show_help(self):
        """Show help"""
        print("""
🔧 Baikon CLI Commands:
   
📝 Basic Commands:
   help           - Show this help message
   quit/exit      - Exit the CLI
   
🔄 Flow Management:
   flows          - List available flows
   functions      - List available functions
   
💾 Session & Data:
   variables/vars - Show current variables
   set <var>=<val>- Set a variable value
   
🚀 Advanced:
   call <function> - Call a function directly
        """)
    
    def _show_variables(self):
        """Show variables"""
        if self.current_context and self.current_context.variables:
            print("📊 Current Variables:")
            for name, value in self.current_context.variables.items():
                print(f"   {name} = {value}")
        else:
            print("📊 No variables set")
    
    def _show_flows(self):
        """Show flows"""
        info = self.engine.get_module_info("main")
        if info:
            print("🔄 Available Flows:")
            for flow_name in info['flows']:
                print(f"   • {flow_name}")
    
    def _show_functions(self):
        """Show functions"""
        info = self.engine.get_module_info("main")
        if info:
            print("⚙️ Available Functions:")
            for func_name in info['functions']:
                print(f"   • {func_name}")
    
    async def _handle_call_command(self, command: str):
        """Handle function calls"""
        try:
            func_name = command[5:].strip()
            
            # Get the module
            module = self.engine.modules.get("main")
            if module and func_name in module.functions:
                function = module.functions[func_name]
                result = await self.engine._call_function(function, module, self.current_context)
                
                if result:
                    for response in result:
                        print(f"🤖 {response}")
                else:
                    print(f"✅ Function {func_name} executed")
            else:
                print(f"❌ Function '{func_name}' not found")
        except Exception as e:
            print(f"❌ Error calling function: {e}")
    
    def _handle_set_command(self, command: str):
        """Handle variable setting"""
        try:
            parts = command[4:].split('=', 1)
            if len(parts) == 2:
                var_name = parts[0].strip()
                value = parts[1].strip().strip('"')
                
                # Try to convert to number
                try:
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    pass
                
                if self.current_context:
                    self.current_context.variables[var_name] = value
                    print(f"✅ Set {var_name} = {value}")
                else:
                    print("❌ No active context")
            else:
                print("❌ Usage: set <variable>=<value>")
        except Exception as e:
            print(f"❌ Error setting variable: {e}")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Baikon CLI v2.0 - Enhanced AI Agent Framework")
    parser.add_argument("file", nargs="?", default="main.flow", 
                       help="Flow file to load (default: main.flow)")
    parser.add_argument("--debug", action="store_true", 
                       help="Enable debug mode")
    
    args = parser.parse_args()
    
    cli = BaikonCLI()
    await cli.start(args.file, args.debug)


if __name__ == "__main__":
    asyncio.run(main())