# Copyright 2014 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""URL routing definitions, and some basic error/warmup handlers."""

import logging

# pylint: disable=relative-import
from core.controllers import admin
from core.controllers import base
from core.controllers import collection_viewer
from core.controllers import editor
from core.controllers import feedback
from core.controllers import galleries
from core.controllers import home
from core.controllers import moderator
from core.controllers import pages
from core.controllers import profile
from core.controllers import reader
from core.controllers import recent_commits
from core.controllers import resources
from core.platform import models
import feconf
# pylint: enable=relative-import

from mapreduce import main as mapreduce_main
from mapreduce import parameters as mapreduce_parameters
import webapp2
from webapp2_extras.routes import RedirectRoute

transaction_services = models.Registry.import_transaction_services()


class FrontendErrorHandler(base.BaseHandler):
    """Handles errors arising from the frontend."""

    REQUIRE_PAYLOAD_CSRF_CHECK = False

    def post(self):
        """Records errors reported by the frontend."""
        logging.error('Frontend error: %s' % self.payload.get('error'))
        self.render_json(self.values)


class WarmupHandler(base.BaseHandler):
    """Handles warmup requests."""

    def get(self):
        """Handles GET warmup requests."""
        pass


def get_redirect_route(regex_route, handler, name, defaults=None):
    """Returns a route that redirects /foo/ to /foo.

    Warning: this method strips off parameters after the trailing slash. URLs
    with parameters should be formulated without the trailing slash.
    """
    if defaults is None:
        defaults = {}
    return RedirectRoute(
        regex_route, handler, name, strict_slash=True, defaults=defaults)


def authorization_wrapper(self, *args, **kwargs):
    # developers.google.com/appengine/docs/python/taskqueue/overview-push
    # promises that this header cannot be set by external callers. If this
    # is present, we can be certain that the request is internal and from
    # the task queue worker.
    if 'X-AppEngine-TaskName' not in self.request.headers:
        self.response.out.write('Forbidden')
        self.response.set_status(403)
        return
    self.real_dispatch(*args, **kwargs)


def ui_access_wrapper(self, *args, **kwargs):
    self.real_dispatch(*args, **kwargs)


MAPREDUCE_HANDLERS = []

for path, handler_class in mapreduce_main.create_handlers_map():
    if path.startswith('.*/pipeline'):
        if 'pipeline/rpc/' in path or path == '.*/pipeline(/.+)':
            path = path.replace('.*/pipeline', '/mapreduce/ui/pipeline')
        else:
            path = path.replace('.*/pipeline', '/mapreduce/worker/pipeline')
    else:
        if '_callback' in path:
            path = path.replace('.*', '/mapreduce/worker', 1)
        elif '/list_configs' in path:
            continue
        else:
            path = path.replace('.*', '/mapreduce/ui', 1)

    if '/ui/' in path or path.endswith('/ui'):
        if (hasattr(handler_class, 'dispatch') and
                not hasattr(handler_class, 'real_dispatch')):
            handler_class.real_dispatch = handler_class.dispatch
            handler_class.dispatch = ui_access_wrapper
        MAPREDUCE_HANDLERS.append((path, handler_class))
    else:
        if (hasattr(handler_class, 'dispatch') and
                not hasattr(handler_class, 'real_dispatch')):
            handler_class.real_dispatch = handler_class.dispatch
            handler_class.dispatch = authorization_wrapper
        MAPREDUCE_HANDLERS.append((path, handler_class))

# Tell map/reduce internals that this is now the base path to use.
mapreduce_parameters.config.BASE_PATH = '/mapreduce/worker'


# Register the URLs with the classes responsible for handling them.
URLS = MAPREDUCE_HANDLERS + [
    get_redirect_route(r'/_ah/warmup', WarmupHandler, 'warmup_handler'),

    get_redirect_route(
        r'/notifications_dashboard', home.NotificationsDashboardPage,
        'notifications_dashboard_handler'),
    get_redirect_route(
        r'/notificationsdashboardhandler/data',
        home.NotificationsDashboardHandler,
        'notifications_dashboard_handler'),
    get_redirect_route(
        r'/my_explorations', home.MyExplorationsPage, 'my_explorations_page'),
    get_redirect_route(
        r'/myexplorationshandler/data', home.MyExplorationsHandler,
        'my_explorations_handler'),

    get_redirect_route(r'/about', pages.AboutPage, 'about_page'),
    get_redirect_route(
        r'/participate', pages.ParticipatePage, 'participate_page'),
    get_redirect_route(
        r'/site_guidelines', pages.ParticipatePage,
        'redirect_to_participate_page'),
    get_redirect_route(
        r'/contact', pages.AboutPage, 'redirect_to_about_page'),

    get_redirect_route(r'/forum', pages.ForumPage, 'forum_page'),
    get_redirect_route(r'/terms', pages.TermsPage, 'terms_page'),
    get_redirect_route(r'/privacy', pages.PrivacyPage, 'privacy_page'),

    get_redirect_route(r'/admin', admin.AdminPage, 'admin_page'),
    get_redirect_route(r'/adminhandler', admin.AdminHandler, 'admin_handler'),
    get_redirect_route(
        r'/adminjoboutput', admin.AdminJobOutput, 'admin_job_output'),
    get_redirect_route(
        r'/admintopicscsvdownloadhandler',
        admin.AdminTopicsCsvDownloadHandler,
        'admin_topics_csv_download_handler'),

    get_redirect_route(
        r'/imagehandler/<exploration_id>/<encoded_filepath>',
        resources.ImageHandler, 'image_handler'),
    get_redirect_route(
        r'/object_editor_template/<obj_type>',
        resources.ObjectEditorTemplateHandler, 'object_editor_template'),
    get_redirect_route(
        r'/value_generator_handler/<generator_id>',
        resources.ValueGeneratorHandler, 'value_generator_handler'),

    get_redirect_route(r'/', galleries.GalleryPage, 'gallery_page'),
    get_redirect_route(
        r'%s' % feconf.GALLERY_URL, galleries.GalleryPage, 'gallery_page'),
    get_redirect_route(
        r'%s' % feconf.GALLERY_DATA_URL, galleries.GalleryHandler,
        'gallery_handler'),

    get_redirect_route(
        r'%s' % feconf.LEARN_GALLERY_URL, galleries.GalleryRedirectPage,
        'learn_gallery_page'),
    get_redirect_route(
        r'%s' % feconf.PLAYTEST_QUEUE_URL, galleries.GalleryRedirectPage,
        'playtest_queue_page'),
    get_redirect_route(
        r'%s' % feconf.CONTRIBUTE_GALLERY_URL, galleries.GalleryRedirectPage,
        'contribute_gallery_page'),
    get_redirect_route(
        r'%s' % feconf.NEW_EXPLORATION_URL,
        galleries.NewExploration, 'new_exploration'),
    get_redirect_route(
        r'%s' % feconf.UPLOAD_EXPLORATION_URL,
        galleries.UploadExploration, 'upload_exploration'),
    get_redirect_route(
        r'/explorationsummarieshandler/data',
        galleries.ExplorationSummariesHandler, 'exploration_summaries_handler'),

    get_redirect_route(
        r'/profile/<username>', profile.ProfilePage, 'profile_page'),
    get_redirect_route(
        r'/profilehandler/data/<username>', profile.ProfileHandler,
        'profile_handler'),
    get_redirect_route(
        r'/preferences', profile.PreferencesPage, 'preferences_page'),
    get_redirect_route(
        r'/preferenceshandler/data', profile.PreferencesHandler,
        'preferences_handler'),
    get_redirect_route(
        r'/preferenceshandler/profile_picture', profile.ProfilePictureHandler,
        'profle_picture_handler'),
    get_redirect_route(
        r'/preferenceshandler/profile_picture_by_username/<username>',
        profile.ProfilePictureHandlerByUsername,
        'profile_picture_handler_by_username'),
    get_redirect_route(
        r'%s' % feconf.SIGNUP_URL, profile.SignupPage, 'signup_page'),
    get_redirect_route(
        r'%s' % feconf.SIGNUP_DATA_URL, profile.SignupHandler,
        'signup_handler'),
    get_redirect_route(
        r'%s' % feconf.USERNAME_CHECK_DATA_URL,
        profile.UsernameCheckHandler, 'username_check_handler'),

    get_redirect_route(
        r'/moderator', moderator.ModeratorPage, 'moderator_page'),
    get_redirect_route(
        r'/moderatorhandler/email_draft/<action>',
        moderator.EmailDraftHandler, 'moderator_action_email_draft'),

    get_redirect_route(
        r'%s/<exploration_id>' % feconf.EXPLORATION_URL_PREFIX,
        reader.ExplorationPage, 'exploration_page'),
    get_redirect_route(
        r'%s/<exploration_id>' % feconf.EXPLORATION_INIT_URL_PREFIX,
        reader.ExplorationHandler, 'exploration_handler'),
    get_redirect_route(
        r'/explorehandler/exploration_start_event/<exploration_id>',
        reader.ExplorationStartEventHandler,
        'exploration_start_event_handler'),
    get_redirect_route(
        r'/explorehandler/state_hit_event/<exploration_id>',
        reader.StateHitEventHandler, 'state_hit_event_handler'),
    get_redirect_route(
        r'/explorehandler/answer_submitted_event/<exploration_id>',
        reader.AnswerSubmittedEventHandler, 'answer_submitted_event_handler'),
    get_redirect_route(
        r'/explorehandler/give_feedback/<exploration_id>',
        reader.ReaderFeedbackHandler, 'reader_feedback_handler'),
    get_redirect_route(
        r'/explorehandler/exploration_complete_event/<exploration_id>',
        reader.ExplorationCompleteEventHandler, 'reader_complete_handler'),
    get_redirect_route(
        r'/explorehandler/exploration_maybe_leave_event/<exploration_id>',
        reader.ExplorationMaybeLeaveHandler, 'reader_leave_handler'),
    get_redirect_route(
        r'/explorehandler/classify/<exploration_id>', reader.ClassifyHandler,
        'reader_classify_handler'),
    get_redirect_route(
        r'/explorehandler/rating/<exploration_id>',
        reader.RatingHandler, 'rating_handler'),
    get_redirect_route(
        r'/explorehandler/recommendations/<exploration_id>',
        reader.RecommendationsHandler, 'recommendations_handler'),

    get_redirect_route(
        r'%s/<exploration_id>' % feconf.EDITOR_URL_PREFIX,
        editor.ExplorationPage, 'editor_exploration_page'),
    get_redirect_route(
        r'/createhandler/data/<exploration_id>', editor.ExplorationHandler,
        'editor_exploration_handler'),
    get_redirect_route(
        r'/createhandler/change_list_summary/<exploration_id>',
        editor.ChangeListSummaryHandler, 'change_list_summary'),
    get_redirect_route(
        r'/createhandler/download/<exploration_id>',
        editor.ExplorationDownloadHandler, 'exploration_download_handler'),
    get_redirect_route(
        r'/createhandler/download_state/<exploration_id>',
        editor.StateDownloadHandler, 'state_download_handler'),
    get_redirect_route(
        r'/createhandler/imageupload/<exploration_id>',
        editor.ImageUploadHandler, 'image_upload_handler'),
    get_redirect_route(
        r'/createhandler/resolved_answers/<exploration_id>/<escaped_state_name>',
        editor.ResolvedAnswersHandler, 'resolved_answers_handler'),
    get_redirect_route(
        r'/createhandler/training_data/<exploration_id>/<escaped_state_name>',
        editor.UntrainedAnswersHandler, 'training_data_handler'),
    get_redirect_route(
        r'/createhandler/resource_list/<exploration_id>',
        editor.ExplorationResourcesHandler, 'exploration_resources_handler'),
    get_redirect_route(
        r'/createhandler/revert/<exploration_id>',
        editor.ExplorationRevertHandler, 'exploration_revert_handler'),
    get_redirect_route(
        r'%s/<exploration_id>' % feconf.EXPLORATION_RIGHTS_PREFIX,
        editor.ExplorationRightsHandler, 'exploration_rights_handler'),
    get_redirect_route(
        r'/createhandler/moderatorrights/<exploration_id>',
        editor.ExplorationModeratorRightsHandler,
        'exploration_moderator_rights_handler'),
    get_redirect_route(
        r'/createhandler/snapshots/<exploration_id>',
        editor.ExplorationSnapshotsHandler, 'exploration_snapshots_handler'),
    get_redirect_route(
        r'/createhandler/statisticsversion/<exploration_id>',
        editor.ExplorationStatsVersionsHandler, 'exploration_stats_versions_handler'),
    get_redirect_route(
        r'/createhandler/statistics/<exploration_id>/<exploration_version>',
        editor.ExplorationStatisticsHandler, 'exploration_statistics_handler'),
    get_redirect_route(
        r'/createhandler/state_rules_stats/<exploration_id>/<escaped_state_name>',
        editor.StateRulesStatsHandler, 'state_rules_stats_handler'),
    get_redirect_route(
        r'/createhandler/started_tutorial_event',
        editor.StartedTutorialEventHandler, 'started_tutorial_event_handler'),

    get_redirect_route(
        r'%s' % feconf.RECENT_COMMITS_DATA_URL,
        recent_commits.RecentCommitsHandler, 'recent_commits_handler'),
    get_redirect_route(
        r'%s' % feconf.RECENT_FEEDBACK_MESSAGES_DATA_URL,
        feedback.RecentFeedbackMessagesHandler,
        'recent_feedback_messages_handler'),

    get_redirect_route(
        r'%s/<exploration_id>' % feconf.FEEDBACK_LAST_UPDATED_URL_PREFIX,
        feedback.FeedbackLastUpdatedHandler, 'feedback_last_updated_handler'),
    get_redirect_route(
        r'%s/<exploration_id>' % feconf.FEEDBACK_THREADLIST_URL_PREFIX,
        feedback.ThreadListHandler, 'feedback_threadlist_handler'),
    get_redirect_route(
        r'%s/<exploration_id>/<thread_id>' % feconf.FEEDBACK_THREAD_URL_PREFIX,
        feedback.ThreadHandler, 'feedback_thread_handler'),
    get_redirect_route(
        r'%s/<exploration_id>' % feconf.SUGGESTION_URL_PREFIX,
        feedback.SuggestionHandler, 'suggestion_handler'),
    get_redirect_route(
        r'%s/<exploration_id>/<thread_id>' %
        feconf.SUGGESTION_ACTION_URL_PREFIX,
        feedback.SuggestionActionHandler, 'suggestion_action_handler'),
    get_redirect_route(
        r'%s/<exploration_id>' % feconf.SUGGESTION_LIST_URL_PREFIX,
        feedback.SuggestionListHandler, 'suggestion_list_handler'),

    get_redirect_route(
        r'%s/<collection_id>' % feconf.COLLECTION_URL_PREFIX,
        collection_viewer.CollectionPage, 'collection_page'),
    get_redirect_route(
        r'%s/<collection_id>' % feconf.COLLECTION_DATA_URL_PREFIX,
        collection_viewer.CollectionDataHandler, 'collection_data_handler'),

    get_redirect_route(
        r'/notificationshandler', home.NotificationsHandler,
        'notifications_handler'),

    get_redirect_route(
        r'/frontend_errors', FrontendErrorHandler, 'frontend_error_handler'),

    get_redirect_route(
        r'/logout', base.LogoutPage, 'logout_page_handler'),

    # 404 error handler.
    get_redirect_route(r'/<:.*>', base.Error404Handler, 'error_404_handler'),
]

app = transaction_services.toplevel_wrapper(  # pylint: disable=invalid-name
    webapp2.WSGIApplication(URLS, debug=feconf.DEBUG))
