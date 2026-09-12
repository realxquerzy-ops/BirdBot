import traceback


async def safe_ack(interaction, text="❌ An error occurred. Please try again."):
    """Make sure the user always gets a reply, even if the handler raised."""
    try:
        if interaction.response.is_done():
            try:
                await interaction.followup.send(text, ephemeral=True)
                return
            except Exception:
                pass
        await interaction.response.send_message(text, ephemeral=True)
    except Exception:
        pass


def log_error():
    traceback.print_exc()


async def setup(bot):
    pass