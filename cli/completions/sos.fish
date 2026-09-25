# fish completion for sos / svoya (SOS «СОС»).  SPDX-License-Identifier: Apache-2.0
# Installed as /usr/share/fish/vendor_completions.d/sos.fish (and svoya.fish).
function __sos_complete
    set -l prev (commandline -opc)
    set -l cur (commandline -ct)
    sos __complete $prev[2..-1] "$cur" 2>/dev/null
end
complete -c sos -f -a '(__sos_complete)'
complete -c svoya -f -a '(__sos_complete)'
