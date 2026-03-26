#!/bin/sh
git filter-branch -f --env-filter '
if [ "$GIT_COMMITTER_EMAIL" = "harshit.j004@gmail.com" ]; then
    export GIT_COMMITTER_NAME="Harshit-J004"
    export GIT_COMMITTER_EMAIL="harsjoshi1004@gmail.com"
fi
if [ "$GIT_AUTHOR_EMAIL" = "harshit.j004@gmail.com" ]; then
    export GIT_AUTHOR_NAME="Harshit-J004"
    export GIT_AUTHOR_EMAIL="harsjoshi1004@gmail.com"
fi
' --tag-name-filter cat -- --branches --tags
