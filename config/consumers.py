from channels.generic.websocket import AsyncJsonWebsocketConsumer

class AuthGroupConsumer(AsyncJsonWebsocketConsumer):
    groups_allow = {"dashboard", "monitoring", "pipeline", "devices", "valves", "notifications"}

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.joined = set()
        await self.accept()

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        group = content.get("group")
        if group not in self.groups_allow:
            await self.send_json({"error": "invalid group"})
            return
        if action == "subscribe" and group not in self.joined:
            await self.channel_layer.group_add(group, self.channel_name)
            self.joined.add(group)
        elif action == "unsubscribe" and group in self.joined:
            await self.channel_layer.group_discard(group, self.channel_name)
            self.joined.discard(group)

    async def broadcast_event(self, event):
        await self.send_json({"event": event["event"], "payload": event["payload"]})

    async def disconnect(self, code):
        for g in getattr(self, "joined", set()):
            await self.channel_layer.group_discard(g, self.channel_name)