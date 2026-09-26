import httpx
import respx

from surprise import images

POSTER = "https://www.billetreduc.com/zg/n1920/vz-1.jpeg"


def test_only_same_site_hosts_are_copied():
    assert images.needs_copy(POSTER)
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


@respx.mock
def test_local_copy_refuses_non_images(tmp_path):
    respx.get(POSTER.replace("n1920", "n800")).respond(200, text="<html>", headers={"Content-Type": "text/html"})
    with httpx.Client() as client:
        assert images.local_copy(POSTER, client, tmp_path) is None
