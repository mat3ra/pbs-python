#!/usr/bin/env bash
# Build _pbs.cpython-310-<arch>-linux-gnu.so against installed Torque (5.x wrap).
# Wrap sources come from mat3ra/surfsara-pbs-python (cloned if SURFSARA_SRC unset).
#
# Intended for CI (AlmaLinux 9 + torque-devel) and local use.
set -euo pipefail

PYTHON="${PYTHON:-python3.10}"
TORQUE_INCLUDE="${TORQUE_INCLUDE:-/usr/local/include/torque}"
TORQUE_LIBDIR="${TORQUE_LIBDIR:-/usr/local/lib64}"
OUT_DIR="${OUT_DIR:-dist}"
SURFSARA_REPO="${SURFSARA_REPO:-https://github.com/mat3ra/surfsara-pbs-python.git}"
SURFSARA_REF="${SURFSARA_REF:-main}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if [[ -z "${SURFSARA_SRC:-}" ]]; then
  SURFSARA_SRC="${ROOT}/.surfsara-pbs-python"
  if [[ ! -f "${SURFSARA_SRC}/src/5.x/pbs_wrap.cxx" ]]; then
    rm -rf "${SURFSARA_SRC}"
    git clone --depth 1 --branch "${SURFSARA_REF}" "${SURFSARA_REPO}" "${SURFSARA_SRC}"
  fi
fi

[[ -f "${SURFSARA_SRC}/src/5.x/pbs_wrap.cxx" ]] \
  || { echo "missing ${SURFSARA_SRC}/src/5.x/pbs_wrap.cxx" >&2; exit 1; }
[[ -f "${TORQUE_INCLUDE}/pbs_ifl.h" ]] || { echo "torque headers not found at ${TORQUE_INCLUDE}" >&2; exit 1; }
[[ -e "${TORQUE_LIBDIR}/libtorque.so" || -e "${TORQUE_LIBDIR}/libtorque.so.2" ]] \
  || { echo "libtorque not found in ${TORQUE_LIBDIR}" >&2; exit 1; }

command -v "${PYTHON}" >/dev/null || { echo "missing ${PYTHON}" >&2; exit 1; }
command -v g++ >/dev/null || { echo "missing g++" >&2; exit 1; }

export TORQUE_INCLUDE TORQUE_LIBDIR
export LD_LIBRARY_PATH="${TORQUE_LIBDIR}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT

mkdir -p "${WORKDIR}/native" "${WORKDIR}/pbs" "${OUT_DIR}"
cp "${SURFSARA_SRC}/src/5.x/pbs_wrap.cxx" "${WORKDIR}/native/"
cp "${SURFSARA_SRC}/src/5.x/"*.h "${WORKDIR}/native/"

# Minimal Extension build; vendored 5.x headers must precede system torque headers.
cat > "${WORKDIR}/setup.py" <<'EOF'
import os
from setuptools import Extension, setup

ext = Extension(
    "pbs._pbs",
    sources=["native/pbs_wrap.cxx"],
    define_macros=[("TORQUE_5", None)],
    include_dirs=["native", os.environ["TORQUE_INCLUDE"]],
    library_dirs=[os.environ["TORQUE_LIBDIR"]],
    runtime_library_dirs=[os.environ["TORQUE_LIBDIR"]],
    libraries=["torque"],
    language="c++",
    extra_compile_args=["-fPIC", "-O2", "-Wno-deprecated-declarations", "-Wno-register"],
)

setup(name="pbs-python-so", version="0.0.0", packages=["pbs"], ext_modules=[ext])
EOF
touch "${WORKDIR}/pbs/__init__.py"

"${PYTHON}" -m pip install --upgrade "setuptools>=61" "wheel" >/dev/null
( cd "${WORKDIR}" && "${PYTHON}" setup.py build_ext --inplace )

SO="$(find "${WORKDIR}/pbs" -maxdepth 1 -name '_pbs.cpython-310-*-linux-gnu.so' | head -1)"
[[ -n "${SO}" && -f "${SO}" ]] || { echo "extension was not produced" >&2; find "${WORKDIR}" -name '_pbs*' >&2; exit 1; }

ARCH="$(uname -m)"
case "${ARCH}" in
  x86_64|amd64) PY_ARCH=x86_64 ;;
  aarch64|arm64) PY_ARCH=aarch64 ;;
  *) PY_ARCH="${ARCH}" ;;
esac
DEST="${OUT_DIR}/_pbs.cpython-310-${PY_ARCH}-linux-gnu.so"
cp -f "${SO}" "${DEST}"

echo "built ${DEST}"
ls -lh "${DEST}"
file "${DEST}" || true
"${PYTHON}" - <<PY
import importlib.util
spec = importlib.util.spec_from_file_location("_pbs", "${DEST}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print("load OK:", "${DEST}")
print("has pbs_connect:", hasattr(mod, "pbs_connect"))
assert hasattr(mod, "pbs_connect")
PY
