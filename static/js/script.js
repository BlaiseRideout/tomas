(function($) {
	$(function() {
		var players = null;

		var OTHERSTRING = "OTHER (PLEASE SPECIFY)";
		var SELECTSTRING = "PLEASE SELECT A PLAYER";
		var NEWPLAYERSTRING = "NEW PLAYER";

		function getPlayers() {
			$.getJSON('/seating/players.json', function(data) {
				players = data;
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
				elem.after("<button class=\"clearplayercomplete\">✖</button>");
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
	});
})(jQuery);
