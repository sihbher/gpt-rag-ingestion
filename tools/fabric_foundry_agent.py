import logging
from typing import Any, Dict, Optional

from dependencies import get_config


class FabricFoundryDataAgentClient:
    """Bridge client to query a published Fabric Data Agent through Foundry Agent Service.

    This class intentionally keeps a small surface area so the API endpoint can call it
    without knowing SDK internals.
    """

    def __init__(self) -> None:
        self._cfg = get_config()
        self.project_endpoint = self._cfg.get("FOUNDRY_PROJECT_ENDPOINT", "", allow_none=True)
        self.model_deployment_name = self._cfg.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")
        self.fabric_project_connection_id = self._cfg.get("FABRIC_PROJECT_CONNECTION_ID", "", allow_none=True)
        self.agent_name = self._cfg.get("FABRIC_AGENT_NAME", "fabric-data-agent-bridge")
        self.agent_instructions = self._cfg.get(
            "FABRIC_AGENT_INSTRUCTIONS",
            "Use the Fabric tool for data questions related to enterprise metrics, products, customers, and sales.",
        )
        self.force_tool_choice = (
            self._cfg.get("FABRIC_FORCE_TOOL_CHOICE", "true").lower() in ("true", "1", "yes")
        )

        self._project_client = None
        self._openai_client = None
        self._agent = None

    def _ensure_sdk_clients(self) -> None:
        if self._project_client and self._openai_client:
            return

        if not self.project_endpoint:
            raise ValueError("FOUNDRY_PROJECT_ENDPOINT is required")
        if not self.fabric_project_connection_id:
            raise ValueError("FABRIC_PROJECT_CONNECTION_ID is required")

        # Deferred imports keep startup lightweight and avoid hard failures for users
        # not enabling the Fabric-Foundry extension path.
        from azure.identity import DefaultAzureCredential
        from azure.ai.projects import AIProjectClient

        self._project_client = AIProjectClient(
            endpoint=self.project_endpoint,
            credential=DefaultAzureCredential(),
        )
        self._openai_client = self._project_client.get_openai_client()

    def _ensure_agent(self) -> None:
        if self._agent is not None:
            return

        self._ensure_sdk_clients()

        from azure.ai.projects.models import (
            PromptAgentDefinition,
            MicrosoftFabricPreviewTool,
            FabricDataAgentToolParameters,
            ToolProjectConnection,
        )

        definition = PromptAgentDefinition(
            model=self.model_deployment_name,
            instructions=self.agent_instructions,
            tools=[
                MicrosoftFabricPreviewTool(
                    fabric_dataagent_preview=FabricDataAgentToolParameters(
                        project_connections=[
                            ToolProjectConnection(
                                project_connection_id=self.fabric_project_connection_id
                            )
                        ]
                    )
                )
            ],
        )

        # Reuse the same in-memory agent reference for subsequent calls.
        self._agent = self._project_client.agents.create_version(
            agent_name=self.agent_name,
            definition=definition,
        )

    def ask(self, question: str, user_token: Optional[str] = None) -> Dict[str, Any]:
        if not question or not question.strip():
            raise ValueError("question must be a non-empty string")

        if user_token:
            logging.info(
                "[fabric-foundry-agent] Received user bearer token; identity passthrough is expected to be handled by Foundry/Fabric connection settings."
            )

        self._ensure_agent()

        request_kwargs: Dict[str, Any] = {
            "input": question,
            "extra_body": {
                "agent_reference": {
                    "name": self._agent.name,
                    "type": "agent_reference",
                }
            },
        }
        if self.force_tool_choice:
            request_kwargs["tool_choice"] = "required"

        response = self._openai_client.responses.create(**request_kwargs)
        answer = getattr(response, "output_text", None)
        if not answer:
            answer = str(response)

        return {
            "answer": answer,
            "agentName": self._agent.name,
            "agentVersion": getattr(self._agent, "version", "unknown"),
            "toolChoiceForced": self.force_tool_choice,
        }
