# Text from the model goes into public comments and pull request bodies through this (#26).
# - "@" gets a zero-width space after it, so nobody is mentioned.
# - A closing keyword (close, fix, resolve and their forms), with or without a colon, before an issue
#   reference (#n, GH-n, owner/repo#n, a github.com URL) gets a
#   zero-width space after it, so merging the pull request cannot close some other issue.
def safe:
  gsub("@"; "@​")
  | gsub("\\b(?<k>close[sd]?|fix(e[sd])?|resolve[sd]?)(?<s>:[ \\t\\n]*|[ \\t\\n]+)(?<t>#|GH-[0-9]|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#|https?://(www\\.)?github\\.com/)"; "\(.k)​\(.s)\(.t)"; "i");
