"""
Mixin for client-side conversation history management.

This mixin provides conversation history tracking for providers that use
stateless APIs (no server-side session management). It stores the full
message history in a LocalConversation object that gets passed back to
the caller for reuse in subsequent requests.

Usage:
    class MyProvider(AsyncGeneratorProvider, LocalConversationMixin):
        manage_conversation_history = True
        
        @classmethod
        async def create_async_generator(cls, model, messages, conversation=None, **kwargs):
            # Get the effective messages (handles history management)
            effective_messages, conversation = cls.prepare_conversation(
                messages, conversation
            )
            
            # Use effective_messages for the API call
            ...
            
            # Accumulate response and yield conversation at the end
            full_response = ""
            async for chunk in api_stream():
                if isinstance(chunk, str):
                    full_response += chunk
                yield chunk
            
            # Update conversation with assistant response and yield it
            cls.finalize_conversation(conversation, full_response)
            yield conversation
"""

from __future__ import annotations

from ...providers.response import JsonConversation
from ...typing import Messages
from ... import debug


class LocalConversation(JsonConversation):
    """
    Conversation object that stores message history client-side.
    
    This is used by providers with stateless APIs to maintain conversation
    continuity across multiple requests.
    
    Attributes:
        message_history: List of all messages in the conversation, each with
                        'role' and 'content' keys.
    """
    
    def __init__(self, **kwargs):
        """Initialize with optional message_history in kwargs."""
        super().__init__(**kwargs)
        # Ensure message_history exists
        if not hasattr(self, 'message_history'):
            self.message_history = []
    
    def get_dict(self) -> dict:
        """Return a dictionary representation including message_history."""
        result = super().get_dict()
        # Ensure message_history is included
        if hasattr(self, 'message_history') and 'message_history' not in result:
            result['message_history'] = self.message_history
        return result


class LocalConversationMixin:
    """
    Mixin that provides client-side conversation history management.
    
    Providers can inherit from this mixin to gain conversation history
    tracking without needing server-side session management.
    
    Class Attributes:
        manage_conversation_history: Set to True to enable history tracking ON THE CLIENT, not the server.
                                     Default is False for backward compatibility.
    """
    
    # Class attribute to opt-in to conversation history management ON THE CLIENT
    manage_conversation_history: bool = False
    
    @classmethod
    def prepare_conversation(
        cls,
        messages: Messages,
        conversation: LocalConversation = None
    ) -> tuple[Messages, LocalConversation]:
        """
        Prepare messages and conversation for a request.
        
        This method handles the conversation history management:
        - If conversation is None, creates a new LocalConversation with all messages
        - If conversation exists, appends only new messages to history
        
        Args:
            messages: The incoming messages for this request
            conversation: Existing conversation object or None
            
        Returns:
            Tuple of (effective_messages, conversation):
            - effective_messages: The full message history to send to the API
            - conversation: The updated conversation object
        """
        if not cls.manage_conversation_history:
            # If not managing history, just return messages as-is
            return messages, conversation
        
        if conversation is None:
            # First message in conversation - store all messages
            conversation = LocalConversation(message_history=list(messages))
            effective_messages = messages
            debug.log(f"LocalConversationMixin: Created new conversation with {len(messages)} messages")
        else:
            # Continuing conversation - append new messages to history
            # Ensure message_history exists (for legacy conversation objects)
            if not hasattr(conversation, 'message_history'):
                conversation.message_history = []
            
            # Append all incoming messages to history
            for msg in messages:
                conversation.message_history.append(msg)
            
            # Use full history for the API call
            effective_messages = list(conversation.message_history)
            debug.log(f"LocalConversationMixin: Appended {len(messages)} messages, total history: {len(effective_messages)}")
            debug.log(f"LocalConversationMixin: Full conversation history: {effective_messages}")
        
        return effective_messages, conversation
    
    @classmethod
    def finalize_conversation(
        cls,
        conversation: LocalConversation,
        assistant_response: str
    ) -> None:
        """
        Finalize the conversation by adding the assistant's response.
        
        This should be called after the full response has been accumulated.
        
        Args:
            conversation: The conversation object to update
            assistant_response: The full text response from the assistant
        """
        if not cls.manage_conversation_history:
            return
        
        if conversation is not None and assistant_response:
            # Ensure message_history exists
            if not hasattr(conversation, 'message_history'):
                conversation.message_history = []
            
            # Append assistant response to history
            conversation.message_history.append({
                "role": "assistant",
                "content": assistant_response
            })
    
    @classmethod
    def get_conversation_history(cls, conversation: LocalConversation) -> Messages:
        """
        Get the message history from a conversation object.
        
        Args:
            conversation: The conversation object
            
        Returns:
            List of messages or empty list if no history
        """
        if conversation is None:
            return []
        if not hasattr(conversation, 'message_history'):
            return []
        return list(conversation.message_history)