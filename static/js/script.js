(function($) {
	$(function() {
		var players = null;

		var OTHERSTRING = "OTHER (PLEASE SPECIFY)";
		var SELECTSTRING = "PLEASE SELECT A PLAYER";
		var NEWPLAYERSTRING = "NEW PLAYER";

		function getPlayers() {
			$.getJSON('players', function(data) {
				players = [];
				for (i = 0; i < data['players'].length; i++) {
					players.push(data['players'][i]['name']);
				}
				populatePlayerComplete();
			}).fail(window.xhrError);
		}
		window.populatePlayerComplete = function(force) {
			if (players === null || force)
				return getPlayers();
			var elem = $("input.playercomplete");
			elem.autocomplete({
				source: players,
				minLength: 2
			});
			if (elem.next(".clearplayercomplete").length === 0) {
				elem.after('<button class="clearplayercomplete">✖</button>');
				elem.each(function(_, complete) {
					$(complete).next(".clearplayercomplete").click(function(clearbutton) {
						$(complete).val("");
					});
				});
			}
		}

		window.xhrError = function(xhr, status, error) {
			console.log(status + ": " + error);
			console.log(xhr);
		}

		/* Names of endpoints that use javascript along with the empty string.
		   These are removed from the end of URL lists to find the base URL.
		 */
	});
})(jQuery);
