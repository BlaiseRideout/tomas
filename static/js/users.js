$(function() {

	var NonValueChangingKeys = {
		'Tab': 1,
		'Shift': 1,
		'Control': 1,
		'Alt': 1,
		'Meta': 1,
		'ArrowRight': 1,
		'ArrowLeft': 1,
		'ArrowUp': 1,
		'ArrowDown': 1,
	}

	function updateUserField(ev) {
		var userrow = $(this).parents(".user"),
			userID = userrow.data("id"),
			colname = $(this).data("colname");
		if (ev && 'type' in ev && ev.type == 'keyup' &&
			NonValueChangingKeys[ev.key]) {
			console.log('Ignoring ' + ev.type + ' event: ' + ev.key)
			return;
		};
		updateUserRecord(null, userID, false);
	};

	function updateUserRecord(deleteID, userID, reload) {
		/* deleteID can be a user record ID to delete it,
		   or 0 to reset the password for the userID,
		   or -1 to add a new user record */

		if (reload === undefined) {
			reload = true
		};
		var attribute = "[data-id='" + userID + "']",
			user = $(".user" + attribute),
			rec = {
				'userID': userID,
				'action': deleteID == null ? 'update' : (
					deleteID == 0 ? 'resetpwd' : (
						deleteID == -1 ? 'add' : 'delete'))
			};
		user.find(".userfield").each(function() {
			rec[$(this).data('colname')] = $(this).val();
			if ($(this).attr('type') == 'number') {
				rec[$(this).data('colname')] = parseInt($(this).val());
			}
			else if ($(this).attr('type') == 'checkbox') {
				rec[$(this).data('colname')] = $(this).prop('checked') ? '1' : '0';
			}
		});
		$.post('users.html', {
				'userdata': JSON.stringify(rec)
			},
			function(data) {
				if (data["message"]) {
					$.notify(data["message"], data["status"]);
					console.log(data["message"]);
				}
				if (data['status'] === 'success') {
					if (reload) {
						location.reload();
					}
					else if (data['redirect']) {
						console.log('Redirecting to ' + data['redirect']);
						$(document.body).load(data['redirect']);
					}
					else {
						user.find(".userfield").removeClass('bad');
						user.find(".userfield").addClass('good');
					}
				}
				else {
					user.find(".userfield").removeClass('good');
					user.find(".userfield").addClass('bad');
				}
			},
			"json");
	};

	function dropInvite() {
		var inviteID = $(this).parents('.invite').data('id'),
			rec = {
				'action': 'drop'
			};
		$.post('invites/' + inviteID, {
				'invitedata': JSON.stringify(rec)
			},
			function(data) {
				if (data["message"]) {
					$.notify(data["message"], data["status"]);
					console.log(data["message"]);
				}
				if (data['status'] === 'success') {
					location.reload();
				}
				else if (data['redirect']) {
					console.log('Redirecting to ' + data['redirect']);
					$(document.body).load(data['redirect']);
				}
			},
			"json");
	};

	$(".userfield").change(updateUserField).keyup(updateUserField);
	$(".adduserbutton").click(function() {
		updateUserRecord(-1, '0', true)
	});
	$(".deluserbutton").click(function() {
		var id = $(this).parents(".user").data("id");
		updateUserRecord(id, id, true)
	});
	$(".resetpwdbutton").click(function() {
		var id = $(this).parents(".user").data("id");
		updateUserRecord(0, id, false)
	});
	$(".dropinvite").click(dropInvite);
});
