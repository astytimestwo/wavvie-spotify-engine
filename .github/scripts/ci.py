"""CI steps that repeat any failure as a GitHub annotation, which can be read without signing in.

usage: python .github/scripts/ci.py test | build | smoke <path to the built app>
"""
import os
import subprocess
import sys


def annotate(title, text):
    message = text[-3000:].replace('%', '%25').replace('\r', '').replace('\n', '%0A')
    print(f'::error title={title}::{message}', flush=True)


def run(command, title, env=None, timeout=None):
    """Run command, echo its output, and annotate a failure. Returns (exit code, output)."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        message = f'{command[0]} did not finish within {timeout} s'
        annotate(title, message)
        return 1, message
    except OSError as error:  # e.g. the build produced no app to launch
        annotate(title, str(error))
        return 1, str(error)
    output = result.stdout + result.stderr
    print(output, flush=True)
    if result.returncode:
        annotate(f'{title} (exit code {result.returncode})', output)
    return result.returncode, output


def test():
    # faulthandler prints every thread's stack if the process crashes, starting with the crashing thread.
    code, output = run([sys.executable, '-X', 'faulthandler', '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                       'Tests failed')
    crash = output.find('Fatal Python error')
    if crash >= 0:
        annotate('Crash', output[crash:crash + 3000])
    if code:
        failures = [block.strip() for block in output.split('=' * 70) if block.strip().startswith(('FAIL:', 'ERROR:'))]
        for block in failures[:8]:
            heading, _, detail = block.partition('\n')
            annotate(heading, detail)
    return code


def build():
    return run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', 'Wavefeed.spec'], 'Build failed')[0]


def smoke(app):
    # The app opens on its setup page (no credentials here), then quits on its own after a moment.
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', WAVVIE_SMOKE_TEST='1')
    return run([os.path.abspath(app)], 'The built app did not start', env=env, timeout=180)[0]


if __name__ == '__main__':
    step = sys.argv[1]
    sys.exit(test() if step == 'test' else build() if step == 'build' else smoke(sys.argv[2]))
