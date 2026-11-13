# frozen_string_literal: true
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 p4535992 and contributors.

module RedmineAiHelperDmsf
  module Patches
    # Persists this extension's fields when AI Helper saves its own settings.
    #
    # The extension fields travel in the same POST as AI Helper's settings, so
    # they are written only after AI Helper reported success (it redirects on
    # success and re-renders the form on failure). A rejected AI Helper form
    # therefore leaves the extension settings untouched.
    module AiHelperSettingsControllerPatch
      # @return [void]
      def update(*args, **kwargs)
        result = super
        if ai_helper_settings_update_succeeded?
          RedmineAiHelperDmsf::Settings.update(params[:redmine_ai_helper_dmsf])
        end
        result
      end

      private

      # @return [Boolean] whether AI Helper accepted and saved its own settings
      def ai_helper_settings_update_succeeded?
        response.respond_to?(:redirect?) && response.redirect?
      end
    end
  end
end
