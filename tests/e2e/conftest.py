import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    # The dashboard boots a Three.js WebGLRenderer at the top of its module; if WebGL
    # is unavailable the module throws before the upload handler registers. Force a
    # software GL backend so headless Chromium always has a working context.
    return {
        **browser_type_launch_args,
        "args": [
            *browser_type_launch_args.get("args", []),
            "--use-angle=swiftshader",
            "--enable-unsafe-swiftshader",
            "--ignore-gpu-blocklist",
            # Let <audio>.play() resolve without a trusted gesture so the music
            # tests can assert the scroll→playback wiring deterministically.
            "--autoplay-policy=no-user-gesture-required",
        ],
    }
