import asyncio
import os
import disnake
from disnake.ext import commands

TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("Переменная DISCORD_TOKEN не установлена")

ROLE_TO_GIVE = 1010140028824981594  # ID роли для выдачи
CHANNEL_ID = 1499400052102270997  # ID канала где только /apply

bot = commands.InteractionBot(intents=disnake.Intents.all())

PROTECTED_ROLES = {ROLE_TO_GIVE}  # Роли, выдача которых разрешена только боту
VOICE_ROLE = 1499396111297679501  # Роль для выдачи при входе на сервер

class ApplicationModal(disnake.ui.Modal):
    def __init__(self):
        components = [
            disnake.ui.TextInput(label="Ваш ник (Как к вам обращаться)", custom_id="name", style=disnake.TextInputStyle.short, max_length=32),
            disnake.ui.TextInput(label="Откуда узнали о сервере?", custom_id="source", style=disnake.TextInputStyle.short, max_length=200),
            disnake.ui.TextInput(label="Согласны ли соблюдать правила сервера?", custom_id="rules", style=disnake.TextInputStyle.short, max_length=200),
            disnake.ui.TextInput(label="Немного о себе", custom_id="about", style=disnake.TextInputStyle.paragraph, max_length=500),
        ]
        super().__init__(title="Заявка на вступление", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        embed = disnake.Embed(title="🔔 Новая заявка", color=disnake.Color.blue())
        embed.add_field(name="Пользователь", value=f"{inter.author.mention} ({inter.author})", inline=False)
        embed.add_field(name="Ник", value=inter.text_values["name"], inline=False)
        embed.add_field(name="Откуда узнали", value=inter.text_values["source"], inline=False)
        embed.add_field(name="Согласие с правилами", value=inter.text_values["rules"], inline=False)
        embed.add_field(name="О себе", value=inter.text_values["about"], inline=False)

        await inter.send(embed=embed, components=[
            disnake.ui.Button(label="Одобрить", style=disnake.ButtonStyle.green, custom_id="approve"),
            disnake.ui.Button(label="Отклонить", style=disnake.ButtonStyle.red, custom_id="deny")
        ])

@bot.slash_command(description="Подать заявку")
async def apply(inter: disnake.ApplicationCommandInteraction):
    if CHANNEL_ID and inter.channel.id != CHANNEL_ID:
        return await inter.send("Эта команда доступна только в канале заявок.", ephemeral=True)
    await inter.response.send_modal(ApplicationModal())

@bot.listen("on_message")
async def delete_non_owner_messages(message):
    if message.author.bot:
        return
    if CHANNEL_ID and message.channel.id == CHANNEL_ID:
        if message.author.id != message.guild.owner_id:
            await message.delete()

@bot.listen("on_button_click")
async def button_listener(inter: disnake.MessageInteraction):
    if inter.component.custom_id not in ["approve", "deny"]: return
    if not inter.author.guild_permissions.administrator:
        return await inter.send("У вас нет прав администратора.", ephemeral=True)

    embed = inter.message.embeds[0]
    mention_text = embed.fields[0].value.split()[0]
    member_id = int(mention_text.strip("<@!>"))
    member = inter.guild.get_member(member_id)
    requested_name = embed.fields[1].value

    if inter.component.custom_id == "approve":
        if member is None:
            return await inter.send("Участник покинул сервер.", ephemeral=True)
        role = inter.guild.get_role(ROLE_TO_GIVE)
        if role: await member.add_roles(role)
        voice_role = inter.guild.get_role(VOICE_ROLE)
        if voice_role and voice_role in member.roles:
            await member.remove_roles(voice_role, reason="Получена роль из заявки")
        if member.id == inter.guild.owner_id:
            nick_result = "Ник не изменен (владелец сервера)."
        else:
            try:
                await member.edit(nick=requested_name)
                nick_result = f"Ник изменен на {requested_name}."
            except Exception as e:
                nick_result = f"Ошибка при смене ника: {e}"
        embed.title = "✅ Заявка одобрена"; embed.color = disnake.Color.green()
        await inter.message.edit(embed=embed, components=[])
        await inter.send(f"✅ Одобрено для {member} ({member.display_name}). {nick_result}", ephemeral=True)
    else:
        embed.title = "❌ Заявка отклонена"; embed.color = disnake.Color.red()
        await inter.message.edit(embed=embed, components=[])
        await inter.send("Отклонено.", ephemeral=True)

@bot.listen("on_member_update")
async def protect_roles(before: disnake.Member, after: disnake.Member):
    added_roles = set(after.roles) - set(before.roles)
    protected_added = [r for r in added_roles if r.id in PROTECTED_ROLES]
    if not protected_added:
        return

    await asyncio.sleep(1)

    async for entry in after.guild.audit_logs(action=disnake.AuditLogAction.member_role_update, limit=10):
        if entry.target.id != after.id:
            continue
        if entry.user.id == bot.user.id:
            return
        for role in protected_added:
            if role in after.roles:
                await after.remove_roles(role, reason="Роль выдана не ботом — автоматическое снятие")
        return

    for role in protected_added:
        if role in after.roles:
            await after.remove_roles(role, reason="Не удалось определить выдавшего — автоматическое снятие")

@bot.listen("on_member_join")
async def on_member_join(member: disnake.Member):
    role = member.guild.get_role(VOICE_ROLE)
    if role:
        await member.add_roles(role, reason="Вход на сервер")

bot.run(TOKEN)