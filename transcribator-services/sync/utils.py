def check_job_id(job_id: str) -> bool:
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-"
    return set(job_id).issubset(set(allowed))