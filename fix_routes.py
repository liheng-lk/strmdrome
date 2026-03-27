import glob, re

for fpath in glob.glob("StrmDrome/api/*.py"):
    with open(fpath, "r") as f:
        content = f.read()

    # Remove def _r(p): ...
    content = re.sub(r'def _r\(p\):.*?\n', '', content)
    content = re.sub(r'def _route\(path\):.*?\n\s+return.*?\n', '', content)
    
    # Replace _route
    content = re.sub(
        r'@router\.api_route\(\*_route\("([^"]+)"\),\s*methods=_METHODS\)',
        r'@router.api_route("/rest/\1", methods=_METHODS)\n@router.api_route("/rest/\1.view", methods=_METHODS)',
        content
    )
    
    # Replace _r
    content = re.sub(
        r'@router\.api_route\(\*_r\("([^"]+)"\),\s*methods=_M\)',
        r'@router.api_route("/rest/\1", methods=_M)\n@router.api_route("/rest/\1.view", methods=_M)',
        content
    )
    
    with open(fpath, "w") as f:
        f.write(content)
print("Regex replace done")
