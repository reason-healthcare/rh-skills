library DiabetesScreeningLibrary version '0.1.0'

using FHIR version '4.0.1'
include FHIRHelpers version '4.0.1'

codesystem "LOINC": 'http://loinc.org'
codesystem "SNOMEDCT": 'http://snomed.info/sct'

valueset "Fasting Plasma Glucose": 'http://example.org/fhir/ValueSet/fasting-plasma-glucose'
valueset "Hemoglobin A1C": 'http://example.org/fhir/ValueSet/hemoglobin-a1c'
valueset "Obesity": 'http://example.org/fhir/ValueSet/obesity'
valueset "Hypertension": 'http://example.org/fhir/ValueSet/hypertension'

context Patient

define "Age35OrOlder":
  AgeInYearsAt(Today()) >= 35

define "HasADiabetesRiskFactor":
  exists([Condition: "Obesity"])
    or exists([Condition: "Hypertension"])
