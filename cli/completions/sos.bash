# bash completion for sos / svoya (SOS «СОС»).  SPDX-License-Identifier: Apache-2.0
# Installed as /usr/share/bash-completion/completions/sos (symlink: svoya).
# Candidates come from `sos __complete <words…>` (modules, apps, models, themes — always current).
_sos() {
  local cur prev_words
  if declare -F _get_comp_words_by_ref >/dev/null; then
    local words cword
    _get_comp_words_by_ref -n : cur words cword
    prev_words=("${words[@]:1:cword-1}")
  else
    cur=${COMP_WORDS[COMP_CWORD]}
    prev_words=("${COMP_WORDS[@]:1:COMP_CWORD-1}")
  fi
  local IFS=$'\n'
  COMPREPLY=($(sos __complete "${prev_words[@]}" "$cur" 2>/dev/null))
  if declare -F __ltrim_colon_completions >/dev/null; then __ltrim_colon_completions "$cur"; fi
}
complete -F _sos sos svoya
