package noosfera.risk.classification

import rego.v1

score := (input.impact * 0.30) + ((1 - input.reversibility) * 0.25) + (input.uncertainty * 0.20) + (input.power_concentration * 0.15) + (input.consciousness_risk * 0.10)

risk_class := "R5" if score >= 0.85
risk_class := "R4" if {
    score >= 0.68
    score < 0.85
}
risk_class := "R3" if {
    score >= 0.50
    score < 0.68
}
risk_class := "R2" if {
    score >= 0.30
    score < 0.50
}
risk_class := "R1" if {
    score > 0
    score < 0.30
}
risk_class := "R0" if score == 0

required_quorum := 5 if risk_class == "R5"
required_quorum := 4 if risk_class == "R4"
required_quorum := 3 if risk_class == "R3"
required_quorum := 2 if risk_class == "R2"
required_quorum := 1 if risk_class == "R1"
required_quorum := 0 if risk_class == "R0"

decision := {"class": risk_class, "score": score, "required_quorum": required_quorum}
