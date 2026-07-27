import io
from typing import List
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from app.models.requirements import Requirement
from app.models.reports import ReportType

class ReportGenerator:
    def __init__(self, regulation_name: str, org_name: str, report_type: ReportType, requirements: List[Requirement]):
        self.regulation_name = regulation_name
        self.org_name = org_name
        self.report_type = report_type
        self.requirements = requirements
        self.styles = getSampleStyleSheet()
        self.title_style = self.styles['Title']
        self.heading_style = self.styles['Heading2']
        self.normal_style = self.styles['Normal']

    def generate_pdf_bytes(self) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        story = []
        
        # 1. Header
        title = f"{self.report_type.value.replace('_', ' ').title()} Report"
        story.append(Paragraph(title, self.title_style))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Regulation: {self.regulation_name}", self.heading_style))
        story.append(Paragraph(f"Organization: {self.org_name}", self.normal_style))
        story.append(Spacer(1, 24))
        
        # 2. Content based on ReportType
        if self.report_type == ReportType.executive_summary:
            story.extend(self._build_executive_summary())
        elif self.report_type == ReportType.technical:
            story.extend(self._build_technical())
        elif self.report_type == ReportType.audit_evidence:
            story.extend(self._build_audit_evidence())
        elif self.report_type == ReportType.gap_analysis:
            story.extend(self._build_gap_analysis())
        elif self.report_type == ReportType.checklist:
            story.extend(self._build_checklist())
            
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    def _build_executive_summary(self):
        # A summary table of counts by severity and type
        story = [Paragraph("Executive Summary of Compliance Posture", self.heading_style), Spacer(1, 12)]
        data = [["Severity", "Count"]]
        sev_counts = {}
        for req in self.requirements:
            sev = req.severity.value
            sev_counts[sev] = sev_counts.get(sev, 0) + 1
        for k, v in sev_counts.items():
            data.append([k.title(), str(v)])
            
        t = Table(data, colWidths=[200, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(t)
        return story

    def _build_technical(self):
        story = [Paragraph("Technical Requirements Detailed View", self.heading_style), Spacer(1, 12)]
        for req in self.requirements:
            story.append(Paragraph(f"<b>{req.title}</b> ({req.severity.value})", self.normal_style))
            story.append(Paragraph(f"Description: {req.description}", self.normal_style))
            story.append(Spacer(1, 12))
        return story

    def _build_audit_evidence(self):
        story = [Paragraph("Audit Evidence Requirements", self.heading_style), Spacer(1, 12)]
        data = [["Requirement ID", "Title", "Evidence Required"]]
        for req in self.requirements:
            evidence = str(req.evidence_required) if req.evidence_required else "None specified"
            data.append([str(req.id)[:8], req.title, evidence])
            
        t = Table(data, colWidths=[100, 150, 200])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ]))
        story.append(t)
        return story

    def _build_gap_analysis(self):
        story = [Paragraph("Gap Analysis Matrix", self.heading_style), Spacer(1, 12)]
        for req in self.requirements:
            story.append(Paragraph(f"<b>Gap for:</b> {req.title}", self.normal_style))
            story.append(Paragraph(f"Current Status: {req.validation_status.value}", self.normal_style))
            story.append(Spacer(1, 6))
        return story

    def _build_checklist(self):
        story = [Paragraph("Compliance Checklist", self.heading_style), Spacer(1, 12)]
        for req in self.requirements:
            story.append(Paragraph(f"[ ] <b>{req.title}</b> - {req.type.value}", self.normal_style))
            story.append(Spacer(1, 6))
        return story
