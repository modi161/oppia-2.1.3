// Copyright 2015 The Oppia Authors. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS-IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * @fileoverview Directive for the fallback editor.
 *
 * @author sean@seanlip.org (Sean Lip)
 */

oppia.directive('fallbackEditor', [function() {
  return {
    restrict: 'E',
    scope: {
      trigger: '=',
      getOnSaveFn: '&onSave',
      outcome: '='
    },
    templateUrl: 'components/fallbackEditor',
    controller: [
      '$scope', 'editabilityService', function($scope, editabilityService) {
        $scope.isEditable = editabilityService.isEditable();

        $scope.editFallbackForm = {};
        $scope.triggerEditorIsOpen = false;

        $scope.INT_FORM_SCHEMA = {
          type: 'int',
          ui_config: {},
          validators: [{
            id: 'is_at_least',
            min_value: 1
          }]
        };

        $scope.triggerMemento = null;

        $scope.openTriggerEditor = function() {
          if ($scope.isEditable) {
            $scope.triggerMemento = angular.copy($scope.trigger);
            $scope.triggerEditorIsOpen = true;
          }
        };

        $scope.saveThisTrigger = function() {
          $scope.triggerEditorIsOpen = false;
          $scope.triggerMemento = null;
          $scope.getOnSaveFn()();
        };

        $scope.cancelThisTriggerEdit = function() {
          $scope.trigger = angular.copy($scope.triggerMemento);
          $scope.triggerMemento = null;
          $scope.triggerEditorIsOpen = false;
        };

        $scope.$on('externalSave', function() {
          if ($scope.triggerEditorIsOpen &&
              $scope.editFallbackForm.editTriggerForm.$valid) {
            $scope.saveThisTrigger();
          }
        });
      }
    ]
  };
}]);
