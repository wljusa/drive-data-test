from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    topic: str
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}\t{self.topic}\t{self.detail}"


@dataclass
class Report:
    findings: list[Finding]

    @property
    def ok(self) -> bool:
        return not self.findings
