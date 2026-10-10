"""
 Image generation slash commands
"""

import random
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont

from bot import global_state
from bot.helper import get_random_color


def _font(size: int):
    """The bundled display font, or Pillow's default if it is not installed."""
    try:
        return ImageFont.truetype(
            global_state.resource_path("Inter-SemiBold.ttf"), size
        )
    except OSError:
        return ImageFont.load_default()


def _colour_swatch(red: int, green: int, blue: int) -> discord.File:
    """A rounded swatch of one colour, labelled with its RGB and hex values."""
    img = PILImage.new("RGB", (500, 500), color=(red, green, blue))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, 200, 55], radius=55 // 2, fill="white")

    font = _font(18)
    draw.text((10, 6), f"RGB: {red}, {green}, {blue}", fill="black", font=font)
    draw.text(
        (10, 26), f"HEX: #{red:02X}{green:02X}{blue:02X}", fill="black", font=font
    )

    # round the corners of the swatch itself
    mask = PILImage.new("L", (500, 500), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 500, 500], radius=55 // 2, fill=255)
    img.putalpha(mask)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename="color.png")


class Image(commands.GroupCog):
    """Image generation commands (the image help category)."""

    @app_commands.command(name="tti", description="Converts given text to image")
    @app_commands.describe(text="The text to convert into image")
    async def text_to_image(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer()

        if not text.startswith(" "):
            text = " " + text
        if not text.endswith(" "):
            text += " "

        # Create image
        font = _font(48)

        # Calculate text size
        img = PILImage.new("RGB", (1, 1), color="black")
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), text, font=font)
        width = int(bbox[2] - bbox[0])
        height = int(bbox[3] - bbox[1])

        # Create final image
        img = PILImage.new("RGB", (width + 20, height + 30), color="black")
        draw = ImageDraw.Draw(img)
        draw.text((10, 5), text, font=font, fill="white")

        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        file = discord.File(buffer, filename="text.png")

        embed = discord.Embed(
            title="Success!",
            description="Here is your image.",
            color=get_random_color(),
        )
        embed.set_image(url="attachment://text.png")

        await interaction.followup.send(embed=embed, file=file)

    @app_commands.command(
        name="makecolor", description="Generates a color based on given RGB values"
    )
    @app_commands.describe(
        red="The red value (0-255)",
        green="The green value (0-255)",
        blue="The blue value (0-255)",
    )
    async def makecolor(
        self, interaction: discord.Interaction, red: int, green: int, blue: int
    ):
        await interaction.response.defer()

        if not (0 <= red <= 255 and 0 <= green <= 255 and 0 <= blue <= 255):
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description="RGB values must be between 0 and 255 (inclusive)!",
                    color=get_random_color(),
                )
            )
            return

        embed = discord.Embed(
            title="Success!",
            description=f"Here's your color for (R:{red}, G:{green}, B:{blue}):-",
            color=discord.Color.from_rgb(red, green, blue),
        )
        embed.set_image(url="attachment://color.png")

        await interaction.followup.send(
            embed=embed, file=_colour_swatch(red, green, blue)
        )

    @app_commands.command(name="randomcolor", description="Generates a random color")
    async def randomcolor(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Generate random RGB values
        red = random.randint(0, 255)
        green = random.randint(0, 255)
        blue = random.randint(0, 255)

        embed = discord.Embed(
            title="Success!",
            description=f"Here's your random color (R:{red}, G:{green}, B:{blue}):-",
            color=discord.Color.from_rgb(red, green, blue),
        )
        embed.set_image(url="attachment://color.png")

        await interaction.followup.send(
            embed=embed, file=_colour_swatch(red, green, blue)
        )

