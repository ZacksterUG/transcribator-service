export interface Patient {
  id: string;
  medicalRecordNumber: string;
  ward: string;
  bed: string;
  fullName: string;
  age: number;
  dateOfBirth: string;
  hospitalizationDate: string;
  departmentDate: string;
  diagnosis: string;
  icdCode: string;
  attendingDoctor: string;
  admissionDate: string;
  admissionDiagnosis: string;
  clinicalDiagnosis: string;
  severity: string;
  healthIndicators: {
    temperature: string;
    bloodPressure: string;
    heartRate: string;
  };
  bloodGroup: string;
  anthropometry: {
    height: number;
    weight: number;
    bmi: number;
  };
}

export interface Note {
  id: string;
  medicalRecordNumber: string;
  createdAt: string;
  doctor: string;
  department: string;
  text: string;
}
