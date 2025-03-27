import argparse
from hashlib import sha1
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
import tempfile

###############################################################################
# Copyright (c) 2022 Marc Schreiber and others.
#
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License 2.0 which is available at
# http://www.eclipse.org/legal/epl-2.0.
#
# SPDX-License-Identifier: EPL-2.0
#
# Contributors:
# Marc Schreiber - initial API and implementation
###############################################################################
DEFAULT_LOMBOK_VERSION = "1.18.36"

# 使用 Path 构建绝对路径
base_dir = Path(__file__).parent.parent
DEFAULT_LOMBOK_JAR = base_dir / f"extensions/lombok/lombok-{DEFAULT_LOMBOK_VERSION}.jar"

def validate_lombok_config(lombok_jar):
    lombok_path = Path(lombok_jar)
    if not lombok_path.exists():
        print(f"Error: Lombok JAR not found at {lombok_jar}")
        sys.exit(1)

def get_java_executable(known_args):
    if known_args.java_executable:
        return known_args.java_executable

    java_executable = 'java'
    if 'JAVA_HOME' in os.environ:
        system = platform.system()
        ext = '.exe' if system == 'Windows' else ''
        java_path = Path(os.environ['JAVA_HOME']) / 'bin' / f'java{ext}'
        if java_path.exists():
            java_executable = str(java_path.resolve())

    if not known_args.validate_java_version:
        return java_executable

    try:
        out = subprocess.check_output([java_executable, '-version'],
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error checking Java version: {e.output}")

    version_match = re.search(r'version\s+"?(\d+)(\.\d+(_\d+)?)?"?', out)
    if not version_match:
        raise RuntimeError("Could not determine Java version")

    java_major_version = int(version_match.group(1))
    if java_major_version < 17:
        raise RuntimeError("jdtls requires at least Java 17")

    return java_executable

def find_equinox_launcher(jdtls_base_directory):
    plugins_dir = jdtls_base_directory / "plugins"
    for launcher in plugins_dir.glob('org.eclipse.equinox.launcher_*.jar'):
        return launcher
    raise RuntimeError("Cannot find equinox launcher")

def get_shared_config_path(jdtls_base_path):
    system = platform.system()
    system_to_config = {
        'Linux': 'config_linux',
        'FreeBSD': 'config_linux',
        'Darwin': 'config_mac',
        'Windows': 'config_win'
    }
    config_dir = system_to_config.get(system)
    if not config_dir:
        raise RuntimeError(f"Unknown platform {system} detected")
    return jdtls_base_path / config_dir

def main(args):
    cwd = Path.cwd()
    cwd_name = cwd.name
    jdtls_data_path = Path(tempfile.gettempdir()) / f"jdtls-{sha1(cwd_name.encode()).hexdigest()}"

    parser = argparse.ArgumentParser()

    parser.add_argument('--lombok-enabled',
                       action='store_true',
                       default=True,
                       help='Enable Lombok support (default: true)')
    parser.add_argument('--no-lombok-enabled',
                       dest='lombok_enabled',
                       action='store_false',
                       help='Disable Lombok support')
    parser.add_argument('--lombok-jar',
                       default=DEFAULT_LOMBOK_JAR,
                       help=f'Path to Lombok JAR (default: {DEFAULT_LOMBOK_JAR})')
    parser.add_argument('--lombok-version',
                       default=DEFAULT_LOMBOK_VERSION,
                       help=f'Lombok version (default: {DEFAULT_LOMBOK_VERSION})')

    parser.add_argument('--validate-java-version',
                       action='store_true',
                       default=True,
                       help='Validate Java version (default: true)')
    parser.add_argument('--no-validate-java-version',
                       dest='validate_java_version',
                       action='store_false',
                       help='Disable Java version validation')
    parser.add_argument('--java-executable',
                       help='Path to java executable used to start runtime')
    parser.add_argument('--jvm-arg',
                       default=[],
                       action='append',
                       help='Additional JVM options (use with equal sign)')
    parser.add_argument('-data',
                       default=jdtls_data_path)

    known_args, args = parser.parse_known_args(args)

    validate_lombok_config(known_args.lombok_jar)
    lombok_jvm_args = [
        f"-javaagent:{known_args.lombok_jar}",
        f"-Xbootclasspath/a:{known_args.lombok_jar}",
        "-Dlog.level=ALL"
    ]
    known_args.jvm_arg = lombok_jvm_args + known_args.jvm_arg

    # Create logs directory
    log_dir = cwd / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    # Add JVM logging arguments
    jvm_log_file = log_dir / 'jvm.log'
    jvm_log_arg = f"-Xlog:all:file={jvm_log_file}:time:filecount=5,filesize=10M"
    known_args.jvm_arg.append(jvm_log_arg)

    if known_args.lombok_enabled:
        args = [
            f"--lombok-support-enabled={str(known_args.lombok_enabled).lower()}",
            f"--lombok-version={known_args.lombok_version}"
        ] + args

    java_executable = get_java_executable(known_args)
    jdtls_base_path = Path(__file__).parent.parent
    shared_config_path = get_shared_config_path(jdtls_base_path)
    jar_path = find_equinox_launcher(jdtls_base_path)

    exec_args = [
        "-Declipse.application=org.eclipse.jdt.ls.core.id1",
        "-Dosgi.bundles.defaultStartLevel=4",
        "-Declipse.product=org.eclipse.jdt.ls.core.product",
        "-Dosgi.checkConfiguration=true",
        f"-Dosgi.sharedConfiguration.area={shared_config_path}",
        "-Dosgi.sharedConfiguration.area.readOnly=true",
        "-Dosgi.configuration.cascaded=true",
        # "-Xms1G",
        "--add-modules=ALL-SYSTEM",
        "--add-opens", "java.base/java.util=ALL-UNNAMED",
        "--add-opens", "java.base/java.lang=ALL-UNNAMED",
    ] + known_args.jvm_arg + [
        "-jar", str(jar_path),
        "-data", str(jdtls_data_path),
    ] + args

    if os.name == 'posix':
        os.execvp(java_executable, exec_args)
    else:
        subprocess.run([java_executable] + exec_args, check=True)

if __name__ == "__main__":
    main(sys.argv[1:])