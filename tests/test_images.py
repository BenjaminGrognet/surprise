import io

import httpx
import respx
from PIL import Image

from surprise import images

POSTER = "https://www.billetreduc.com/zg/n1920/vz-1.jpeg"


def test_only_same_site_hosts_are_copied():
    assert images.needs_copy(POSTER)
    assert images.needs_copy("https://cdn.sortiraparis.com/images/80/113614/1278045-campagne.jpg")  # Referer checked
    assert not images.needs_copy("https://cdn.example.com/a.jpg") and not images.needs_copy(None)


@respx.mock
def test_local_copy_downloads_once(tmp_path):
    # The 1920 px poster is fetched in its 800 px size.
    route = respx.get(POSTER.replace("n1920", "n800")).respond(200, content=b"jpeg", headers={"Content-Type": "image/jpeg"})
    with httpx.Client() as client:
        first = images.local_copy(POSTER, client, tmp_path)
        again = images.local_copy(POSTER, client, tmp_path)
    assert first == again and first.suffix == ".jpg" and first.read_bytes() == b"jpeg"
    assert route.call_count == 1


def _picture(size, mode="RGB", kind="JPEG"):
    out = io.BytesIO()
    image = Image.new(mode, size, (180, 40, 90, 128) if mode == "RGBA" else (180, 40, 90))
    for x in range(0, size[0], 7):  # some detail, as a photo has
        image.putpixel((x, x % size[1]), (255, 255, 255, 255) if mode == "RGBA" else (255, 255, 255))
    image.save(out, kind, quality=97) if kind == "JPEG" else image.save(out, kind)
    return out.getvalue()


@respx.mock
def test_a_copy_is_made_lighter_for_a_phone(tmp_path):
    # A 3000 px photo comes down to 1200 px on its longer side, a JPEG lighter than the original.
    big = _picture((3000, 2000))
    respx.get("https://www.billetreduc.com/a.jpg").respond(200, content=big, headers={"Content-Type": "image/jpeg"})
    # A PNG with transparency stays a PNG (a JPEG would blacken it), resized too.
    clear = _picture((2400, 1200), "RGBA", "PNG")
    respx.get("https://www.billetreduc.com/b.png").respond(200, content=clear, headers={"Content-Type": "image/png"})
    with httpx.Client() as client:
        photo = images.local_copy("https://www.billetreduc.com/a.jpg", client, tmp_path)
        logo = images.local_copy("https://www.billetreduc.com/b.png", client, tmp_path)
    with Image.open(photo) as shown:
        assert shown.format == "JPEG" and max(shown.size) == images.MAX_SIDE and shown.size == (1200, 800)
    assert photo.suffix == ".jpg" and photo.stat().st_size < len(big)
    with Image.open(logo) as shown:
        assert shown.format == "PNG" and shown.mode == "RGBA" and shown.size == (1200, 600)
    # Found again by its address, whatever its new format.
    assert images.copied("https://www.billetreduc.com/b.png", tmp_path) == logo


def test_a_small_or_moving_image_is_kept_as_it_is():
    small = _picture((300, 200), kind="PNG")
    content, suffix = images.lighter(small, ".png")
    assert suffix in (".png", ".jpg") and len(content) <= len(small)
    assert images.lighter(b"GIF89a...", ".gif") == (b"GIF89a...", ".gif")
    assert images.lighter(b"not an image", ".jpg") == (b"not an image", ".jpg")


@respx.mock
def test_local_copy_refuses_non_images(tmp_path):
    respx.get(POSTER.replace("n1920", "n800")).respond(200, text="<html>", headers={"Content-Type": "text/html"})
    with httpx.Client() as client:
        assert images.local_copy(POSTER, client, tmp_path) is None


@respx.mock
def test_an_image_shows_on_another_site_or_not():
    respx.get("https://cdn.example.com/ok.jpg").respond(200, content=b"x", headers={"Content-Type": "image/jpeg"})
    respx.get("https://cdn.example.com/dead.jpg").respond(404, text="non")
    respx.get("https://cdn.example.com/own.jpg").respond(200, headers={"Content-Type": "image/jpeg", "Cross-Origin-Resource-Policy": "same-site"})
    respx.get("https://cdn.example.com/busy.jpg").respond(429)
    with httpx.Client() as client:
        assert images.loads(client, "https://cdn.example.com/ok.jpg") is True
        assert images.loads(client, "https://cdn.example.com/dead.jpg") is False
        assert images.loads(client, "https://cdn.example.com/own.jpg") is False
        assert images.loads(client, "https://cdn.example.com/busy.jpg") is None  # asked again later, never shown meanwhile
