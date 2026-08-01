"""
diagnose_mcp.py
Run this in your terminal: python diagnose_mcp.py
"""
import asyncio
import json
import sys
from pathlib import Path

async def test_stdio_server(name: str, config: dict):
    print(f"\n🔌 Testing stdio server: {name}")
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        
        params = StdioServerParameters(
            command=config["command"],
            args=config.get("args", []),
            env=config.get("env"),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                tools = getattr(result, "tools", result)
                print(f"✅ Success! Found {len(tools)} tools.")
                for tool in tools[:5]:  # Print first 5
                    print(f"   - {tool.name}")
                if len(tools) > 5:
                    print(f"   ... and {len(tools) - 5} more")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")

async def test_http_server(name: str, config: dict):
    print(f"\n🔌 Testing HTTP/SSE server: {name}")
    try:
        # Try official mcp SSE client first
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
            async with sse_client(config["url"]) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    tools = getattr(result, "tools", result)
                    print(f"✅ Success (via mcp.client.sse)! Found {len(tools)} tools.")
                    return
        except ImportError:
            pass
        except Exception as e:
            print(f"⚠️ mcp.client.sse failed: {e}")

        # Fallback to fastmcp
        try:
            from fastmcp import Client
            async with Client(config["url"]) as client:
                tools = await client.list_tools()
                print(f"✅ Success (via fastmcp)! Found {len(tools)} tools.")
                return
        except ImportError:
            pass
        except Exception as e:
            print(f"⚠️ fastmcp failed: {e}")
            
        print("❌ Could not connect. Ensure 'mcp' or 'fastmcp' is installed.")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")

async def main():
    config_path = Path("mcp_servers.json")
    if not config_path.exists():
        config_path = Path("chatbot/mcp_servers.json")
        
    if not config_path.exists():
        print("❌ mcp_servers.json not found in current directory or chatbot/")
        sys.exit(1)

    print(f"📂 Reading config from: {config_path.resolve()}")
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    servers = data.get("mcpServers", data)
    if not servers:
        print("⚠️ No servers defined in mcp_servers.json")
        return
        
    for name, config in servers.items():
        if "command" in config:
            await test_stdio_server(name, config)
        elif "url" in config:
            await test_http_server(name, config)
        else:
            print(f"\n⚠️ Server '{name}' has neither 'command' nor 'url'")

if __name__ == "__main__":
    asyncio.run(main())