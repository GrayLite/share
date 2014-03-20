#!/usr/bin/env python

import sys
sys.path.append(sys.path[0] + '/..')
from util import *

import os as OS

dir_root = ''
dir_src = ''
dir_script = sys.path[0]

patches = {
    'src': [
        '0001-Enable-GN-build-for-Android-x64.patch',
        '0002-Fix-build-issues-in-android_webview-for-Android-x64.patch',
        '0003-Add-x86_64-ucontext-structure-for-Android-x64.patch',
        '0004-Fix-type-conversion-issues-for-Android-x64.patch'
    ],
    'src/breakpad/src': ['0001-breakpad-Enable-x86_64-for-android.patch'],
    'src/third_party/icu': ['0001-third_party-icu-x64-support.patch'],
    'src/third_party/lss': [
        '0001-lss-fix-the-__unused-issue.patch',
        '0002-lss-fix-__off64_t-issue.patch'
    ],
    'src/third_party/mesa/src': ['0001-disable-log2.patch'],
    'src/v8': ['0001-v8-x64-support.patch'],
    'ndk': [
        '0001-ndk-Add-gyp-files.patch',
        '0002-ndk-fix-for-Android-x64.patch',
    ],
}

################################################################################


def handle_option():
    global args
    parser = argparse.ArgumentParser(description='Script to sync, build upstream x64 Chromium',
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     epilog='''
examples:
  python %(prog)s --clean -s --patch -b
  python %(prog)s --test-build
  python %(prog)s --test-build --sync-upstream
''')

    parser.add_argument('--clean', dest='clean', help='clean patches and local changes', action='store_true')
    parser.add_argument('-s', '--sync', dest='sync', help='sync the repo', action='store_true')
    parser.add_argument('--sync-upstream', dest='sync_upstream', help='sync with upstream', action='store_true')
    parser.add_argument('--patch', dest='patch', help='apply patches', action='store_true')
    parser.add_argument('-b', '--build', dest='build', help='build', action='store_true')
    parser.add_argument('--build-fail', dest='build_fail', help='allow n build failures before it stops', default='0')
    parser.add_argument('--skip-mk', dest='skip_mk', help='skip the generation of makefile', action='store_true')
    parser.add_argument('--build-debug', dest='build_debug', help='do a Debug build', action='store_true')
    parser.add_argument('--set-ndk', dest='set_ndk', help='set up ndk', action='store_true')
    parser.add_argument('--test-build', dest='test_build', help='build test', action='store_true')

    parser.add_argument('-d', '--dir_root', dest='dir_root', help='set root directory')

    args = parser.parse_args()

    if len(sys.argv) <= 1:
        parser.print_help()
        quit()


def setup():
    global dir_root, dir_src

    if not args.dir_root:
        dir_root = get_symbolic_link_dir()
    else:
        dir_root = args.dir_root

    dir_src = dir_root + '/src'
    os.chdir(dir_root)


def clean(force=False):
    if not args.clean and not force:
        return

    if not force:
        warning('Clean is very dangerous, your local changes will be lost')
        sys.stdout.write('Are you sure to do the cleanup? [yes/no]: ')
        choice = raw_input().lower()
        if choice not in ['yes', 'y']:
            return

    cmd = 'gclient revert -n -j16'
    execute(cmd, show_progress=True)

    backup_dir('ndk')
    cmd = bashify('git reset --hard $(git log --oneline|tail -1|awk \'{print $1}\') && rm -rf android_tools_ndk.gyp crazy_linker.gyp .git')
    execute(cmd)
    restore_dir()


def sync(force=False):
    if not args.sync and not force:
        return

    cmd = 'gclient sync -f -n -j16'
    if not args.sync_upstream:
        rev = '63a3e1a08f173831624289e36a4697b729a590c4'
        cmd += ' --revision src@' + rev
    result = execute(cmd, show_progress=True)
    if result[0]:
        error('sync failed', error_code=result[0])

    cmd = 'gclient runhooks'
    result = execute(cmd, show_progress=True)
    if result[0]:
        error('sync failed', error_code=result[0])


def patch(force=False):
    if not args.patch and not force:
        return

    set_ndk(force=True)

    for repo in patches:
        backup_dir(repo)
        for patch in patches[repo]:
            patch_path = dir_script + '/patches/' + patch
            file = open(patch_path)
            lines = file.readlines()
            file.close()

            pattern = re.compile('Subject: \[PATCH.*\] (.*)')
            match = pattern.search(lines[3])
            title = match.group(1)
            result = execute('git show -s --pretty="format:%s" --max-count=30 |grep "' + title + '"', show_command=False)
            if result[0]:
                cmd = 'git am ' + patch_path
                result = execute(cmd, show_progress=True)
                if result[0]:
                    error('Fail to apply patch ' + patch, error_code=result[0])
            else:
                info('Patch ' + patch + ' was applied before, so is just skipped here')
        restore_dir()


def build(force=False):
    if not args.build and not force:
        return

    if not args.skip_mk:
        backup_dir(dir_src)
        command = bashify('. build/android/envsetup.sh && android_gyp -Dtarget_arch=x64 -Dwerror=')
        execute(command, show_progress=True)
        restore_dir()

    target = 'Release'
    if args.build_debug:
        target = 'Debug'

    ninja_cmd = 'ninja -k' + args.build_fail + ' -j16 -C src/out/' + target + ' android_webview_test_apk android_webview_unittests_apk android_webview_apk'
    ninja_cmd += ' 2>&1 |tee ' + dir_root + '/build.log'
    result = execute(ninja_cmd, show_progress=True)
    if result[0]:
        error('Fail to execute command: ' + ninja_cmd, error_code=result[0])


def set_ndk(force=False):
    if not args.set_ndk and not force:
        return

    if not OS.path.exists('ndk'):
        error('Please put ndk under ' + get_symbolic_link_dir())

    if not OS.path.exists('ndk/platforms/android-19/arch-x86_64'):
        execute('ln -s ../android-20/arch-x86_64 ndk/platforms/android-19/arch-x86_64')

    if not OS.path.islink('src/third_party/android_tools/ndk'):
        # Create symbolic link to real ndk
        if not OS.path.exists('src/third_party/android_tools/ndk_bk'):
            cmd = 'mv src/third_party/android_tools/ndk src/third_party/android_tools/ndk_bk'
        else:
            cmd = 'rm -rf src/third_party/android_tools/ndk'
        execute(cmd, show_command=True)
        backup_dir('src/third_party/android_tools')
        execute('ln -s ../../../ndk ./', show_command=False)
        restore_dir()

    # Init a git repo
    if not OS.path.exists('ndk/.git'):
        backup_dir('ndk')
        execute('git init && git add . && git commit -a -m "orig"')
        restore_dir()


def test_build():
    if not args.test_build:
        return

    clean(force=True)
    sync(force=True)
    patch(force=True)
    build(force=True)


if __name__ == '__main__':
    handle_option()
    setup()
    clean()
    sync()
    set_ndk()
    patch()
    build()
    test_build()
