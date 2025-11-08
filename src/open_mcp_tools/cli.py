"""
Open MCP Tools Server CLI entry point.

Supports both HTTP/SSE (for web clients) and stdio (for Claude Desktop).
"""

import sys
import asyncio
import json
import logging
from typing import Optional

import uvicorn
from .server import app
from .handlers import (
    handle_initialize,
    handle_initialized,
    handle_ping,
    handle_set_level,
    handle_tools_list,
)
from .handlers.resource_handler import handle_resources_list
from .handlers.tool_handler import handle_tools_call
from .core.types import JSONRPCRequest
from .core.responses import ErrorCodes, success_response, error_response
from .payment_handler import PaymentHandler
from .utils.conversion import convert_keys_to_snake_case

logger = logging.getLogger(__name__)


async def handle_stdio_request(data: dict) -> dict:
    """Handle a single JSON-RPC request via stdio"""
    try:
        # Normalize request
        data = convert_keys_to_snake_case(data)
        mcp_request = JSONRPCRequest(**data)
        
        method = mcp_request.method
        params = mcp_request.params or {}
        
        # Protocol methods
        if method == "initialize":
            result = await handle_initialize(params)
            return success_response(mcp_request.id, result)
        
        elif method == "notifications/initialized":
            handle_initialized()
            return success_response(mcp_request.id, {})
        
        elif method == "ping":
            return success_response(mcp_request.id, handle_ping())
        
        elif method == "logging/setLevel":
            level = params.get("level", "info")
            return success_response(mcp_request.id, handle_set_level(level))
        
        # Tools
        elif method == "tools/list":
            result = handle_tools_list()
            # result is a ListToolsResult object - convert to dict
            return success_response(mcp_request.id, result.to_camel_dict() if hasattr(result, 'to_camel_dict') else result.dict())
        
        elif method == "tools/call":
            # For stdio, we need to collect the final result
            payment_handler = PaymentHandler()
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            # Create a minimal mock request for stdio mode
            from fastapi import Request
            from unittest.mock import MagicMock
            mock_request = MagicMock(spec=Request)
            mock_request.headers = {}
            mock_request.state = MagicMock()
            
            tool_generator = handle_tools_call(
                request=mock_request,
                tool_name=tool_name,
                arguments=arguments,
                request_id=str(mcp_request.id),
                payment_handler=payment_handler,
                progress_token=None,
            )
            
            # Collect final result (tools yield JSONRPCResponse objects)
            final_response = None
            async for response in tool_generator:
                final_response = response
            
            if final_response:
                # Response is already a JSONRPCResponse - convert to dict
                return final_response.to_camel_dict()
            else:
                return error_response(mcp_request.id, ErrorCodes.INTERNAL_ERROR, "Tool execution produced no response")
        
        # Resources
        elif method == "resources/list":
            result = handle_resources_list()
            resources = [r.mcp_resource.to_camel_dict() for r in result.resources]
            return success_response(mcp_request.id, {"resources": resources})
        
        elif method == "resources/read":
            from .handlers.resource_handler import handle_resources_read
            uri = params.get("uri", "")
            result = handle_resources_read(uri)
            return success_response(mcp_request.id, result.to_camel_dict())
        
        else:
            return error_response(
                mcp_request.id,
                ErrorCodes.METHOD_NOT_FOUND,
                f"Unknown method: {method}"
            )
    
    except Exception as e:
        logger.error(f"Error handling stdio request: {e}", exc_info=True)
        request_id = data.get("id", "unknown")
        return error_response(
            request_id,
            ErrorCodes.INTERNAL_ERROR,
            f"Internal error: {str(e)}"
        )


def stdio_server():
    """Run MCP server in stdio mode for Claude Desktop"""
    # Suppress startup banner for stdio mode
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logger.setLevel(logging.WARNING)
    
    while True:
        try:
            # Read JSON-RPC request from stdin (synchronous)
            line = sys.stdin.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue
            
            # Parse JSON-RPC request
            request_data = json.loads(line)
            
            # Handle request (run async handler in event loop)
            response = asyncio.run(handle_stdio_request(request_data))
            
            # Write response to stdout
            print(json.dumps(response), flush=True)
        
        except json.JSONDecodeError as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": ErrorCodes.PARSE_ERROR,
                    "message": f"Parse error: {str(e)}"
                }
            }
            print(json.dumps(error_response), flush=True)
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": ErrorCodes.INTERNAL_ERROR,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error_response), flush=True)


def main():
    """Main CLI entry point - starts the Open MCP Tools Server"""
    # Check if running in stdio mode (for Claude Desktop)
    if len(sys.argv) > 1 and sys.argv[1] == "stdio":
        # Run in stdio mode
        stdio_server()
    else:
        # Run in HTTP/SSE mode (default)
        print("\n" + "─" * 60)
        print("  Open MCP Tools Server v0.1 | http://localhost:7284/mcp")
        print("  General-purpose MCP server with extensible tool modules")
        print("─" * 60 + "\n")

        uvicorn.run(
            app,
            host="0.0.0.0",
            port=7284,
            log_level="info",
            timeout_keep_alive=30 * 60,
            timeout_graceful_shutdown=30,
        )


if __name__ == "__main__":
    main()
