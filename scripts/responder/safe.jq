# Text from the model goes into public comments and pull request bodies through this (#26).
# - "@" gets a zero-width space after it, so nobody is mentioned.
# - A closing keyword (close, fix, resolve and their forms), with or without a colon, before an issue
#   reference (#n, GH-n, owner/repo#n, a github.com URL) gets a
#   zero-width space after it, so merging the pull request cannot close some other issue.
def safe:
  gsub("@"; "@​")
  | gsub("\\b(?<k>close[sd]?|fix(e[sd])?|resolve[sd]?)(?<s>:[ \\t\\n]*|[ \\t\\n]+)(?<t>#|GH-[0-9]|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#|https?://(www\\.)?github\\.com/)"; "\(.k)​\(.s)\(.t)"; "i");

# A changed path shown in a pull request body, inside a code span (#53). The path comes from the
# model's change, so it can't end the span (no backtick) or start a new line (no CR or LF), and it
# goes through safe for the @ and closing keywords. The replacing comes first: a CR between
# "Closes" and "#5" would otherwise hide the keyword from safe. They become spaces, not "_": a word
# character in front of "Closes" would take away the word boundary safe looks for.
def safe_path:
  gsub("[`\\r\\n]"; " ") | safe;
