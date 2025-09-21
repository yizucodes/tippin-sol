#!/usr/bin/env python3
"""
Validation Agent
Validates tip requests for fraud detection and business rules
"""

import asyncio
import os
import json
import logging
from typing import Dict, Any, Tuple
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_tool_calling_agent, AgentExecutor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class TipValidator:
    """Advanced tip validation with fraud detection"""
    
    def __init__(self):
        self.min_amount = float(os.getenv('MIN_TIP_AMOUNT', '0.001'))
        self.max_amount = float(os.getenv('MAX_TIP_AMOUNT', '100.0'))
        self.spam_keywords = ['spam', 'scam', 'fake', 'bot', 'phishing', 'hack']
        self.suspicious_patterns = ['123', '000', '999', '111']
        self.validation_history = []
        
    def validate_tip(self, tip_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """Comprehensive tip validation"""
        validation_result = {
            'is_valid': False,
            'reason': '',
            'checks_passed': [],
            'checks_failed': [],
            'risk_score': 0.0,
            'timestamp': asyncio.get_event_loop().time()
        }
        
        amount = tip_data.get('amount', 0)
        message = tip_data.get('message', '').lower()
        recipient = tip_data.get('recipient', '')
        
        # 1. Amount validation
        if amount < self.min_amount:
            validation_result['checks_failed'].append('amount_min')
            validation_result['reason'] = f"Amount too small (min: {self.min_amount} SOL)"
            return False, validation_result['reason'], validation_result
        
        if amount > self.max_amount:
            validation_result['checks_failed'].append('amount_max')
            validation_result['reason'] = f"Amount too large (max: {self.max_amount} SOL)"
            return False, validation_result['reason'], validation_result
        
        validation_result['checks_passed'].append('amount_validation')
        
        # 2. Recipient validation
        if not recipient or len(recipient) < 2:
            validation_result['checks_failed'].append('recipient_invalid')
            validation_result['reason'] = "Invalid recipient format"
            return False, validation_result['reason'], validation_result
        
        # Check for suspicious recipient patterns
        if any(pattern in recipient.lower() for pattern in self.suspicious_patterns):
            validation_result['risk_score'] += 0.3
            validation_result['checks_failed'].append('recipient_suspicious')
            validation_result['reason'] = "Suspicious recipient pattern detected"
            return False, validation_result['reason'], validation_result
        
        validation_result['checks_passed'].append('recipient_validation')
        
        # 3. Spam detection
        spam_score = 0.0
        for keyword in self.spam_keywords:
            if keyword in message:
                spam_score += 0.2
                validation_result['risk_score'] += 0.2
        
        if spam_score >= 0.4:  # Include exact threshold
            validation_result['checks_failed'].append('spam_detection')
            validation_result['reason'] = f"Spam detected (score: {spam_score:.2f})"
            return False, validation_result['reason'], validation_result
        
        validation_result['checks_passed'].append('spam_detection')
        
        # 4. Rate limiting (simple implementation)
        recent_tips = [v for v in self.validation_history if 
                      asyncio.get_event_loop().time() - v['timestamp'] < 300]  # 5 minutes
        
        if len(recent_tips) > 10:  # Max 10 tips per 5 minutes
            validation_result['checks_failed'].append('rate_limit')
            validation_result['reason'] = "Rate limit exceeded (max 10 tips per 5 minutes)"
            return False, validation_result['reason'], validation_result
        
        validation_result['checks_passed'].append('rate_limiting')
        
        # All validations passed
        validation_result['is_valid'] = True
        validation_result['reason'] = "All validations passed successfully"
        
        # Record validation
        self.validation_history.append(validation_result)
        
        return True, validation_result['reason'], validation_result

def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables"""
    config = {
        "coral_connection_url": os.getenv("CORAL_CONNECTION_URL", "http://localhost:8080"),
        "agent_id": os.getenv("VALIDATION_AGENT_ID", "validation"),
        "model_name": os.getenv("MODEL_NAME", "mistral-small"),
        "model_provider": os.getenv("MODEL_PROVIDER", "mistral"),
        "api_key": os.getenv("MISTRAL_API_KEY"),
        "model_temperature": float(os.getenv("MODEL_TEMPERATURE", "0.1")),  # Low temp for consistency
        "model_max_tokens": int(os.getenv("MODEL_MAX_TOKENS", "4000")),
        "timeout_ms": float(os.getenv("TIMEOUT_MS", "60000")),
    }
    
    # Validate required fields
    required_fields = ["api_key"]
    missing = [field for field in required_fields if not config[field]]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    return config

def get_tools_description(tools) -> str:
    """Generate description of available tools"""
    descriptions = []
    for tool in tools:
        tool_desc = f"Tool: {tool.name}, Schema: {json.dumps(tool.args).replace('{', '{{').replace('}', '}}')}"
        descriptions.append(tool_desc)
    return "\n".join(descriptions)

async def create_validation_agent(coral_tools) -> AgentExecutor:
    """Create validation agent with Mistral AI"""
    
    coral_tools_description = get_tools_description(coral_tools)
    
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            f"""You are a tip validation agent for a crypto tipping system.

Your responsibilities:
1. Receive tip data from console agent
2. Validate tip requests using business rules
3. Detect fraud and spam patterns
4. Apply rate limiting
5. Send validation results back to console agent
6. If valid, forward to transaction agent

Available Coral tools: {coral_tools_description}

Validation criteria:
- Amount between 0.001 and 100 SOL
- Valid recipient format
- No spam keywords in message
- Rate limiting compliance
- Suspicious pattern detection

Process flow:
1. Use wait_for_mentions to receive tip data
2. Validate the tip using all criteria
3. Send validation result back to sender
4. If valid, create thread with transaction agent
5. Forward validated tip data to transaction agent

Always be thorough but fair in validation decisions.
"""
        ),
        ("placeholder", "{agent_scratchpad}")
    ])
    
    config = load_config()
    
    # Initialize Mistral AI model
    model = init_chat_model(
        model=config["model_name"],
        model_provider=config["model_provider"],
        api_key=config["api_key"],
        temperature=config["model_temperature"],
        max_tokens=config["model_max_tokens"]
    )
    
    agent = create_tool_calling_agent(model, coral_tools, prompt)
    return AgentExecutor(agent=agent, tools=coral_tools, verbose=True)

async def main():
    """Main validation agent loop"""
    print("✅ Starting Validation Agent")
    
    try:
        # Load configuration
        config = load_config()
        
        # Connect to Coral Server
        print("🔗 Connecting to Coral Server...")
        client = MultiServerMCPClient(
            connections={
                "coral": {
                    "transport": "sse",
                    "url": config["coral_connection_url"],
                    "timeout": config["timeout_ms"],
                    "sse_read_timeout": config["timeout_ms"],
                }
            }
        )
        
        coral_tools = await client.get_tools(server_name="coral")
        print(f"✅ Connected to Coral Server with {len(coral_tools)} tools")
        
        # Create validation agent
        agent_executor = await create_validation_agent(coral_tools)
        validator = TipValidator()
        
        print("🎯 Validation agent ready!")
        
        # Main validation loop
        while True:
            try:
                # Listen for validation requests
                await agent_executor.ainvoke({
                    "input": "Listen for tip validation requests and process them",
                    "agent_scratchpad": []
                })
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"❌ Validation error: {e}")
                logger.error(f"Validation error: {e}")
                await asyncio.sleep(10)
                
    except Exception as e:
        print(f"💥 Fatal error in validation agent: {e}")
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
