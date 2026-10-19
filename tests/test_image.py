"""The image commands: argument validation and the file that comes back.

Pillow runs offline, so these drive the real drawing code rather than a stub.
The swatch itself is covered in test_objects; what is here is what each command
decides -- whether the values are acceptable, and whether a file is sent.
"""

import pytest

from bot.commands.image_commands import Image
from tests.conftest import FakeInteraction


@pytest.fixture
def image():
    return Image()


def sent(interaction: FakeInteraction) -> list:
    return interaction.followups


async def test_a_colour_in_range_is_drawn_and_sent(image):
    interaction = FakeInteraction()

    await image.makecolor.callback(image, interaction, 12, 34, 56)

    assert "R:12, G:34, B:56" in sent(interaction)[0].description


async def test_the_colour_embed_carries_the_swatch_as_an_attachment(image):
    interaction = FakeInteraction()

    await image.makecolor.callback(image, interaction, 1, 2, 3)

    assert sent(interaction)[0].image.url == "attachment://color.png"


@pytest.mark.parametrize(
    ("red", "green", "blue"),
    [(256, 0, 0), (0, 256, 0), (0, 0, 256), (-1, 0, 0)],
)
async def test_colour_values_outside_the_byte_range_are_refused(
    image, red, green, blue
):
    interaction = FakeInteraction()

    await image.makecolor.callback(image, interaction, red, green, blue)

    assert sent(interaction)[0].title == "Error!"
    assert "between 0 and 255" in sent(interaction)[0].description


async def test_the_command_defers_before_doing_the_work(image):
    """Drawing takes long enough that the three second window would lapse."""
    interaction = FakeInteraction()

    await image.makecolor.callback(image, interaction, 1, 2, 3)

    assert interaction.deferred is True


async def test_a_random_colour_is_a_valid_colour(image):
    interaction = FakeInteraction()

    await image.randomcolor.callback(image, interaction)

    assert sent(interaction)[0].title == "Success!"
    assert sent(interaction)[0].image.url == "attachment://color.png"


async def test_text_becomes_an_image_of_its_own(image):
    interaction = FakeInteraction()

    await image.text_to_image.callback(image, interaction, "hello")

    assert sent(interaction)[0].image.url == "attachment://text.png"


async def test_text_is_padded_with_spaces_for_the_font(image):
    """The drawn text is never flush against the edge of the image."""
    interaction = FakeInteraction()

    await image.text_to_image.callback(image, interaction, "hello")

    assert sent(interaction)[0].description == "Here is your image."


async def test_an_empty_string_still_produces_an_image(image):
    interaction = FakeInteraction()

    await image.text_to_image.callback(image, interaction, "")

    assert sent(interaction)[0].title == "Success!"


def test_the_font_helper_falls_back_when_the_font_is_missing(monkeypatch):
    """A missing font file is a bare OSError, not a crash waiting to happen."""
    from bot.commands import image_commands

    monkeypatch.setattr(
        image_commands.ImageFont,
        "truetype",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("no font")),
    )
    monkeypatch.setattr(image_commands.ImageFont, "load_default", lambda *a: "default")

    assert image_commands._font(18) == "default"


def test_the_font_helper_loads_the_bundled_font_at_the_requested_size():
    from bot.commands import image_commands

    font = image_commands._font(18)

    assert font.size == 18
