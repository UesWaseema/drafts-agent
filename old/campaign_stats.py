import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("DRAFTS_DB_HOST")
USER = os.getenv("DRAFTS_DB_USER")
PASS = os.getenv("DRAFTS_DB_PASS")
MAILWIZZ_DB = os.getenv("MAILWIZZ_DB_NAME")
INTERSPIRE_DB = os.getenv("INTERSPIRE_DB_NAME")

def get_mailwizz_campaign_stats(limit=None):
    conn = pymysql.connect(
        host=HOST, user=USER, password=PASS, database=MAILWIZZ_DB,
        cursorclass=pymysql.cursors.DictCursor
    )
    with conn.cursor() as cursor:
        query = """
            SELECT
              c.campaign_id,
              c.campaign_uid,
              c.name        AS campaign_name,
              c.subject,
              c.from_name   AS journal,
              c.from_email,
              c.send_at,
              t.content     AS email_body,

              /* engagement tallies */
              COALESCE(o.opens ,0)   AS opens,
              COALESCE(u.clicks,0)   AS clicks,
              COALESCE(b.bounces,0)  AS bounces,

              /* reliable sent-count from delivery logs */
              COALESCE(s.sent_count, 0) AS sent_count

            FROM mw_campaign c

            LEFT JOIN mw_campaign_template t
                   ON t.campaign_id = c.campaign_id

            /* opens */
            LEFT JOIN (
                SELECT campaign_id, COUNT(DISTINCT subscriber_id) AS opens
                FROM mw_campaign_track_open
                GROUP BY campaign_id
            ) o ON o.campaign_id = c.campaign_id

            /* clicks */
            LEFT JOIN (
                SELECT cu.campaign_id, COUNT(DISTINCT tu.subscriber_id) AS clicks
                FROM mw_campaign_url cu
                JOIN mw_campaign_track_url tu ON tu.url_id = cu.url_id
                GROUP BY cu.campaign_id
            ) u ON u.campaign_id = c.campaign_id

            /* bounces */
            LEFT JOIN (
                SELECT campaign_id, COUNT(DISTINCT subscriber_id) AS bounces
                FROM mw_campaign_bounce_log
                GROUP BY campaign_id
            ) b ON b.campaign_id = c.campaign_id

            /* reliable sent-count */
            LEFT JOIN (
                SELECT campaign_id, COUNT(*) AS sent_count
                FROM mw_campaign_delivery_log
                WHERE status = 'success'
                GROUP BY campaign_id
                UNION ALL
                SELECT campaign_id, COUNT(*) AS sent_count
                FROM mw_campaign_delivery_log_archive
                WHERE status = 'success'
                GROUP BY campaign_id
            ) s ON s.campaign_id = c.campaign_id

            WHERE c.status = 'sent'
            HAVING sent_count > 13
        """
        if limit is not None:
            query += " ORDER BY c.send_at DESC LIMIT %s"
            cursor.execute(query, (limit,))
        else:
            query += " ORDER BY c.send_at DESC"
            cursor.execute(query)

        return cursor.fetchall()



def get_interspire_campaign_stats(limit=None):
    inter_conn = pymysql.connect(
        host=HOST, user=USER, password=PASS, database=INTERSPIRE_DB,
        cursorclass=pymysql.cursors.DictCursor
    )
    with inter_conn.cursor() as cursor:
        base_query = """
            SELECT 
                n.newsletterid,
                n.name AS campaign_name,
                n.subject,
                n.textbody,
                FROM_UNIXTIME(n.createdate) AS created_date,
                FROM_UNIXTIME(s.starttime) AS sent_date,
                s.sendsize,
                s.linkclicks,
                (s.emailopens_unique + s.textopens_unique) AS total_opens,
                s.bouncecount_hard,
                SUBSTRING_INDEX(u.username, '@', -1) AS domain
            FROM is_newsletters n
            LEFT JOIN is_stats_newsletters s ON s.newsletterid = n.newsletterid
            LEFT JOIN is_users u ON s.sentby = u.userid
            WHERE s.sendsize >= 10
        """
        if limit is not None:
            base_query += " ORDER BY n.createdate DESC LIMIT %s"
            cursor.execute(base_query, (limit,))
        else:
            base_query += " ORDER BY n.createdate DESC"
            cursor.execute(base_query)

        base = cursor.fetchall()

        # Unique opens
        cursor.execute("""
            SELECT statid, COUNT(DISTINCT subscriberid) AS unique_opens
            FROM is_stats_emailopens
            GROUP BY statid
        """)
        unique_opens = {row['statid']: row['unique_opens'] for row in cursor.fetchall()}

        # Unique clicks
        cursor.execute("""
            SELECT statid, COUNT(DISTINCT subscriberid) AS unique_clicks
            FROM is_stats_linkclicks
            GROUP BY statid
        """)
        unique_clicks = {row['statid']: row['unique_clicks'] for row in cursor.fetchall()}

        enriched = []
        for row in base:
            statid = row['newsletterid']  # Assuming 1:1 mapping
            u_opens = unique_opens.get(statid, 0)
            u_clicks = unique_clicks.get(statid, 0)
            sendsize = row['sendsize']

            row['unique_opens'] = u_opens
            row['unique_clicks'] = u_clicks
            row['open_rate'] = round((u_opens / sendsize) * 100, 2)
            row['click_rate'] = round((u_clicks / sendsize) * 100, 2)

            enriched.append(row)

        return enriched
