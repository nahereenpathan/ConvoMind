"""HTML and Plain-Text Email Templates for ConvoMind Notifications."""

from typing import Dict, Any, Tuple, Optional
from app.core.config import settings


def _email_wrapper(title: str, preheader: str, body_content: str, cta_url: Optional[str] = None, cta_text: Optional[str] = None) -> str:
    """Wrap content in a clean, modern HTML layout compatible with all major email clients."""
    app_url = settings.APP_BASE_URL.rstrip("/")
    cta_html = ""
    if cta_url and cta_text:
        cta_html = f"""
        <div style="margin: 28px 0; text-align: center;">
          <a href="{cta_url}" style="background-color: #4f46e5; color: #ffffff; padding: 12px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block; box-shadow: 0 2px 4px rgba(79,70,229,0.2);">
            {cta_text}
          </a>
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f5f7; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.6;">
  <div style="display: none; max-height: 0px; overflow: hidden; mso-hide: all;">
    {preheader}
  </div>
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f5f7; padding: 30px 15px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
          <!-- Header -->
          <tr>
            <td style="background-color: #0f172a; padding: 24px 32px; text-align: left;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <span style="color: #6366f1; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">ConvoMind</span>
                    <span style="color: #94a3b8; font-size: 13px; font-weight: 500; margin-left: 8px;">AI Meeting Intelligence</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body Content -->
          <tr>
            <td style="padding: 32px;">
              <h2 style="margin-top: 0; color: #0f172a; font-size: 20px; font-weight: 700;">{title}</h2>
              {body_content}
              {cta_html}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; padding: 20px 32px; border-top: 1px solid #f1f5f9; text-align: center; color: #64748b; font-size: 12px;">
              <p style="margin: 0 0 8px 0;">This email was sent automatically by <strong>ConvoMind</strong>.</p>
              <p style="margin: 0;">
                <a href="{app_url}/settings/notifications" style="color: #6366f1; text-decoration: underline;">Manage Notification Preferences</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def render_email_template(event_type: str, data: Dict[str, Any]) -> Tuple[str, str, str]:
    """Generate (subject, body_text, body_html) for a given event_type and data payload.

    Supported event_types:
    - meeting_invitation
    - meeting_reminder
    - meeting_update
    - meeting_cancelled
    - post_meeting_summary
    - ai_insights_ready
    - recording_ready
    - action_item_assigned
    - follow_up_draft
    """
    app_base = settings.APP_BASE_URL.rstrip("/")
    meeting_id = data.get("meeting_id", "")
    meeting_title = data.get("meeting_title", "ConvoMind Meeting")
    host_name = data.get("host_name", "Host")
    scheduled_at = data.get("scheduled_at", "")
    join_url = data.get("join_url", f"{app_base}/meeting/{meeting_id}" if meeting_id else app_base)
    agenda = data.get("agenda", "")

    if event_type == "meeting_invitation":
        subject = f"Invitation: {meeting_title}"
        preheader = f"You are invited to join {meeting_title} hosted by {host_name}."
        html_body = f"""
        <p>Hello,</p>
        <p><strong>{host_name}</strong> has invited you to join the following meeting:</p>
        <div style="background-color: #f8fafc; border-left: 4px solid #6366f1; padding: 16px; margin: 20px 0; border-radius: 0 8px 8px 0;">
          <h3 style="margin: 0 0 8px 0; color: #0f172a; font-size: 16px;">{meeting_title}</h3>
          {f'<p style="margin: 0 0 6px 0; color: #475569; font-size: 14px;"><strong>Time:</strong> {scheduled_at}</p>' if scheduled_at else ''}
          {f'<p style="margin: 0; color: #475569; font-size: 14px;"><strong>Agenda:</strong> {agenda}</p>' if agenda else ''}
        </div>
        <p>Click below to join the meeting room when ready.</p>
        """
        text_body = f"Invitation: {meeting_title}\n\n{host_name} has invited you to join: {meeting_title}\nScheduled Time: {scheduled_at}\n\nJoin URL: {join_url}"
        return subject, text_body, _email_wrapper(subject, preheader, html_body, cta_url=join_url, cta_text="Join Meeting Now")

    elif event_type == "meeting_reminder":
        time_until = data.get("time_until", "soon")
        subject = f"Reminder ({time_until}): {meeting_title}"
        preheader = f"Your meeting '{meeting_title}' starts in {time_until}."
        html_body = f"""
        <p>Hello,</p>
        <p>This is a reminder that your meeting is starting in <strong>{time_until}</strong>.</p>
        <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 16px; margin: 20px 0; border-radius: 0 8px 8px 0;">
          <h3 style="margin: 0 0 8px 0; color: #0f172a; font-size: 16px;">{meeting_title}</h3>
          {f'<p style="margin: 0; color: #475569; font-size: 14px;"><strong>Scheduled:</strong> {scheduled_at}</p>' if scheduled_at else ''}
        </div>
        """
        text_body = f"Reminder ({time_until}): {meeting_title}\n\nYour meeting is starting in {time_until}.\nScheduled: {scheduled_at}\n\nJoin URL: {join_url}"
        return subject, text_body, _email_wrapper(subject, preheader, html_body, cta_url=join_url, cta_text="Join Meeting")

    elif event_type == "meeting_update":
        subject = f"Updated: {meeting_title}"
        preheader = f"Details for '{meeting_title}' have been updated."
        change_summary = data.get("change_summary", "The meeting details or scheduled time have been updated.")
        html_body = f"""
        <p>Hello,</p>
        <p>The host has updated the details for <strong>{meeting_title}</strong>.</p>
        <div style="background-color: #fefce8; border-left: 4px solid #eab308; padding: 16px; margin: 20px 0; border-radius: 0 8px 8px 0;">
          <p style="margin: 0; color: #854d0e; font-size: 14px;"><strong>Updates:</strong> {change_summary}</p>
          {f'<p style="margin: 8px 0 0 0; color: #475569; font-size: 14px;"><strong>New Time:</strong> {scheduled_at}</p>' if scheduled_at else ''}
        </div>
        """
        text_body = f"Updated: {meeting_title}\n\n{change_summary}\nNew Time: {scheduled_at}\n\nJoin URL: {join_url}"
        return subject, text_body, _email_wrapper(subject, preheader, html_body, cta_url=join_url, cta_text="View Updated Meeting")

    elif event_type == "meeting_cancelled":
        subject = f"Cancelled: {meeting_title}"
        preheader = f"The meeting '{meeting_title}' has been cancelled."
        reason = data.get("reason", "This meeting has been cancelled by the host.")
        html_body = f"""
        <p>Hello,</p>
        <p>Please note that the following meeting has been <strong>cancelled</strong>:</p>
        <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 16px; margin: 20px 0; border-radius: 0 8px 8px 0;">
          <h3 style="margin: 0 0 8px 0; color: #991b1b; font-size: 16px;">{meeting_title}</h3>
          <p style="margin: 0; color: #7f1d1d; font-size: 14px;">{reason}</p>
        </div>
        """
        text_body = f"Cancelled: {meeting_title}\n\n{reason}\nScheduled Time: {scheduled_at}"
        return subject, text_body, _email_wrapper(subject, preheader, html_body)

    elif event_type == "post_meeting_summary":
        subject = f"Meeting Summary: {meeting_title}"
        preheader = f"Executive summary and key insights for {meeting_title}."
        summary_text = data.get("summary", "AI transcription and executive summary have been generated.")
        decisions = data.get("decisions", [])
        decisions_html = ""
        if decisions:
            items = "".join([f"<li style='margin-bottom: 6px;'>{d}</li>" for d in decisions])
            decisions_html = f"<h4>Key Decisions:</h4><ul>{items}</ul>"
        
        detail_url = f"{app_base}/dashboard/meetings/{meeting_id}" if meeting_id else app_base
        html_body = f"""
        <p>Hello,</p>
        <p>Here is your executive summary for <strong>{meeting_title}</strong>:</p>
        <div style="background-color: #f8fafc; border-left: 4px solid #10b981; padding: 16px; margin: 20px 0; border-radius: 0 8px 8px 0;">
          <p style="margin: 0 0 12px 0; color: #334155; font-size: 14px; white-space: pre-line;">{summary_text}</p>
          {decisions_html}
        </div>
        <p>Log in to ConvoMind to explore interactive transcripts, key topics, and full AI intelligence.</p>
        """
        text_body = f"Meeting Summary: {meeting_title}\n\nSummary:\n{summary_text}\n\nView details: {detail_url}"
        return subject, text_body, _email_wrapper(subject, preheader, html_body, cta_url=detail_url, cta_text="View Full Meeting Details")

    elif event_type == "ai_insights_ready":
        subject = f"AI Intelligence Ready: {meeting_title}"
        preheader = f"AI summary, action items, and topic extraction completed for {meeting_title}."
        detail_url = f"{app_base}/dashboard/meetings/{meeting_id}?tab=intelligence" if meeting_id else app_base
        html_body = f"""
        <p>Hello,</p>
        <p>ConvoMind AI has finished processing <strong>{meeting_title}</strong>.</p>
        <p>Your meeting transcript, automated action items, key decisions, and topic breakdowns are now ready for review.</p>
        """
        text_body = f"AI Intelligence Ready: {meeting_title}\n\nAI processing completed for {meeting_title}.\n\nView Intelligence: {detail_url}"
        return subject, text_body, _email_wrapper(subject, preheader, html_body, cta_url=detail_url, cta_text="Explore AI Intelligence")

    elif event_type == "recording_ready":
        subject = f"Recording Ready: {meeting_title}"
        preheader = f"The native audio/video recording for {meeting_title} is ready."
        duration = data.get("duration", "")
        detail_url = f"{app_base}/dashboard/meetings/{meeting_id}?tab=recording" if meeting_id else app_base
        html_body = f"""
        <p>Hello,</p>
        <p>The recording for <strong>{meeting_title}</strong> has been processed and securely saved.</p>
        {f'<p><strong>Duration:</strong> {duration}</p>' if duration else ''}
        <p>You can watch the recording, review synced transcripts, or download media from your dashboard.</p>
        """
        text_body = f"Recording Ready: {meeting_title}\n\nThe recording for {meeting_title} is now available.\n\nWatch Recording: {detail_url}"
        return subject, text_body, _email_wrapper(subject, preheader, html_body, cta_url=detail_url, cta_text="Watch Recording")

    elif event_type == "action_item_assigned":
        subject = f"Action Item Assigned: {meeting_title}"
        preheader = f"You were assigned an action item from {meeting_title}."
        task_text = data.get("task_description", "New action item")
        assignee_name = data.get("assignee_name", "You")
        due_date = data.get("due_date", "")
        detail_url = f"{app_base}/dashboard/meetings/{meeting_id}?tab=action-items" if meeting_id else app_base
        html_body = f"""
        <p>Hello {assignee_name},</p>
        <p>You have been assigned an action item from <strong>{meeting_title}</strong>:</p>
        <div style="background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 16px; margin: 20px 0; border-radius: 0 8px 8px 0;">
          <p style="margin: 0; font-size: 15px; font-weight: 600; color: #1e3a8a;">{task_text}</p>
          {f'<p style="margin: 6px 0 0 0; color: #3b82f6; font-size: 13px;"><strong>Due Date:</strong> {due_date}</p>' if due_date else ''}
        </div>
        """
        text_body = f"Action Item Assigned: {meeting_title}\n\nTask: {task_text}\nDue: {due_date}\n\nView Action Items: {detail_url}"
        return subject, text_body, _email_wrapper(subject, preheader, html_body, cta_url=detail_url, cta_text="View Action Item")

    elif event_type == "follow_up_draft":
        subject = f"Follow-up Email Sent: {meeting_title}"
        preheader = f"Approved follow-up email sent for {meeting_title}."
        draft_body = data.get("follow_up_content", "")
        recipients = data.get("recipients", [])
        recipients_str = ", ".join(recipients) if recipients else "Meeting Participants"
        detail_url = f"{app_base}/dashboard/meetings/{meeting_id}" if meeting_id else app_base
        html_body = f"""
        <p>Hello,</p>
        <p>The human-approved follow-up email for <strong>{meeting_title}</strong> has been delivered to <strong>{recipients_str}</strong>.</p>
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 16px; margin: 20px 0; border-radius: 8px;">
          <p style="margin: 0; color: #334155; font-size: 14px; white-space: pre-line;">{draft_body}</p>
        </div>
        """
        text_body = f"Follow-up Email Sent: {meeting_title}\n\nSent to: {recipients_str}\n\nContent:\n{draft_body}"
        return subject, text_body, _email_wrapper(subject, preheader, html_body, cta_url=detail_url, cta_text="View Meeting Details")

    else:
        # Default fallback
        subject = data.get("subject", f"Notification from ConvoMind: {meeting_title}")
        body = data.get("body", "You have a new notification from ConvoMind.")
        html_body = f"<p>{body}</p>"
        text_body = body
        return subject, text_body, _email_wrapper(subject, subject, html_body)
