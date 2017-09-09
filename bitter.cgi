#!/usr/bin/perl -w

# written by andrewt@cse.unsw.edu.au September 2015
# http://cgi.cse.unsw.edu.au/~cs2041/assignments/bitter/
# ACKNOWLDGEMENTS: Use of Materialize CSS http://materializecss.com/


use CGI qw/:all/;
use CGI::Carp qw/fatalsToBrowser warningsToBrowser/;
use CGI::Cookie;
use CGI::Session;


sub main() {
    #### DEFINING GLOBAL VARIABLES
    ## which determine the page to load

    $logging_out = param('logging_out');
    
    $debug = 1;
    $dataset_size = "medium";
    $users_dir = "dataset-$dataset_size/users";
    $bleats_dir = "dataset-$dataset_size/bleats";

    $searched = param('search_query') || '';
    $bleat_searched = param('bleat_search_query') || '';
    
    #tests if showing homepage or a user page
    my $user_to_show;
    my $page = "home";
    if (defined(param('page'))) { $page = param('page'); }
    if (defined(param('user'))) { $user_to_show = param('user');
    } else { $user_to_show = $curr_user; }
    
    #Setting [un]listen_attempt variable such that page redirects
    #  to the same page where the listen happened
    $listen_attempt = param('listen_user') || '';
    $unlisten_attempt = param('unlisten_user') || '';
    $listened_from_search = param('search_listen') || '';
    $unlistened_from_search = param('search_unlisten') || '';
    $listened_from_user = param('userpage_listen') || '';
    $unlistened_from_user = param('userpage_unlisten') || '';
    if ($listened_from_search) {
        $searched = param('curr_search');
        $listen_attempt = $listened_from_search;
    } elsif ($unlistened_from_search) {
        $searched = param('curr_search');
        $unlisten_attempt = $unlistened_from_search;
    }
    if ($listened_from_user) {
        $listen_attempt = $listened_from_user;
        $page = "user";
        $user_to_show = $listened_from_user;
    } elsif ($unlistened_from_user) {
        $unlisten_attempt = $unlistened_from_user;
        $page = "user";
        $user_to_show = $unlistened_from_user;
    }

    #Get username and password from textfields
    $entered_username = param('username_field') || '';
    $entered_password = param('password_field') || '';


    #retrieving current session
    $sesh = CGI::Session->load() or die CGI::Session->errstr();
    
    $curr_user = $sesh->param('username');
    $logged_in = $sesh->param('_isLoggedIn');

    
    #If curr_user is attempting to listen to another user,
    # these changes are made before page loaded
    if ($listen_attempt) { make_listen($curr_user, $listen_attempt); }
	if ($unlisten_attempt) { make_unlisten($curr_user, $unlisten_attempt); }

    #IF USER IS ATTEMPTING TO LOG IN
    if ($entered_username || $entered_password) {
        if (validate_pw($entered_username, $entered_password) eq 1) { #SUCCESSFUL LOGIN
            #Setting up Session ID
            $session = CGI::Session->new();
            $session->param('username', $entered_username);
            $session->param('_isLoggedIn', 'true');
            $session->expire('_isLoggedIn', '+20m');
            $session->expire('+1d');
            $CGISESSID = $session->id();
            $cookie = CGI::Cookie->new(-name=>$session->name(), -value=>$session->id());
            print redirect(-uri=>"bitter.cgi", -cookie=>$cookie, @_);
            print page_header();
            warningsToBrowser(1);
            CGI::Session->name("BITTER_SESSION");
            print nav_bar(0, $entered_username);
            print user_page("$users_dir/$entered_username");
        } else { #UNSUCCESSFULY LOGIN - show login page
            print page_header();
            warningsToBrowser(1);
            CGI::Session->name("BITTER_SESSION");
            print nav_bar(1);
            
            print login_page();

            $error_msg = validate_pw($entered_username, $entered_password);
            print "<p class=\"flow-text\">$error_msg</p>";
        }
    } elsif ($logging_out eq 1) {
        $sesh->delete();
        $sesh->flush();
        
        print page_header();
        warningsToBrowser(1);
        CGI::Session->name("BITTER_SESSION");
        print nav_bar(1);

        print login_page();
        
    } elsif ($logged_in) { #IF ALREADY LOGGED IN - decide page     
        print page_header();
        warningsToBrowser(1);
        CGI::Session->name("BITTER_SESSION");
        print nav_bar(0, $curr_user); 
    
        #write new bleats if necessary
        my $new_bleat = param('new_bleat_area') || '';
        my $new_reply = param('reply_text') || '';
        my $in_reply_to = param('in_reply_to') || '';
        if ($new_reply) {
            new_bleat($new_reply, $in_reply_to);
        }
        if ($new_bleat) {
            new_bleat($new_bleat);
        }

        #delete bleats if necessary
        my $delete_bleat_id = param('delete_bleat') || '';
        if ($delete_bleat_id) {
            delete_bleat($delete_bleat_id);
        }

        if ($bleat_searched) {
            print bleat_search_results($bleat_searched);
        } elsif ($searched) {
            print search_results($searched);
        } elsif ($page eq "home") {
            print newsfeed($curr_user);
        } elsif ($page eq "user") {
            print user_page("$users_dir/$user_to_show");
        }

    
    } else { #IF NOT LOGGED IN - show login screen
        print page_header();
        warningsToBrowser(1);
        CGI::Session->name("BITTER_SESSION");
        print nav_bar(1);

        print login_page();
    }

    #IMPORTING JAVASCRIPT FILES
    print "<script type=\"text/javascript\" src=\"https://code.jquery.com/jquery-2.1.1.min.js\"></script>\n";
    print "<script type=\"text/javascript\" src=\"materialize.min.js\"></script>";

}

#DELETES THE BLEAT OF THE INPUTTED ID
sub delete_bleat {
    my ($id) = @_;
    unlink "$bleats_dir/$id";
    my $bleat_dir = "$users_dir/$curr_user/bleats.txt";
    open A, "<$bleat_dir" or die "can not open $bleat_dir: $!";
    my @new_bleat_file = ();
    foreach my $line (<A>) {
        chomp $line;
        if ($id !~ /$line/) {
            push(@new_bleat_file, $line);
        }
    }
    close A;

    open (my $fh, '>', $bleat_dir) or die "can not open file $bleat_dir: $!";
    foreach my $bleat (@new_bleat_file) {
        print $fh "$bleat\n";
    }
    close $fh;
}

#GENERATES AN UNUSED BLEAT ID FOR NEW BLEATS
sub generate_bleat_id {
    my $largest = "";
    foreach my $line(glob "$bleats_dir/*") {
        $largest = $line;
        $largest =~ s/^$bleats_dir\///;
    }
    $largest += 5;
    return $largest;
}

#GENERATES NEW BLEAT OF THE PASSED IN MESSAGE
sub new_bleat {
    my ($new_bleat, $in_reply_to) = @_;
    my @new_bleat_info = ();
    push (@new_bleat_info, "bleat: $new_bleat");
    push (@new_bleat_info, "username: $curr_user");
    
    #Collect information to put in new bleat file
    my $details_dir = "$users_dir/$curr_user/details.txt";
    open A, "<$details_dir" or die "can not open $details_dir: $!";
    my $latt = "";
    my $long = "";
    foreach my $line (<A>) {
        if ($line =~ /^home_latitude/) {
            $latt = $line;
            $latt =~ s/^home_latitude: //;
            chomp $latt;
        }
        if ($line =~ /^home_longitude/) {
            $long = $line;
            $long =~ s/^home_longitude: //;
            chomp $long;
        }
    }
    close A;

    if ($latt) { push (@new_bleat_info, "latitude: $latt"); }
    if ($long) { push (@new_bleat_info, "longitude: $long"); }
    $time = time;
    push (@new_bleat_info, "time: $time");

    if ($in_reply_to) { push (@new_bleat_info, "in_reply_to: $in_reply_to") };
    
    my $new_bleat_id = generate_bleat_id();

    my $new_bleat_dir = "$bleats_dir/$new_bleat_id";
    open (my $fh, '>', $new_bleat_dir) or die "Could not open file $new_bleat_dir $!";
    $new_bleat = join("\n", @new_bleat_info);
    
    $new_bleat .= "\n";
    print $fh $new_bleat;
    close $fh;

    ##Rewrite the bleat file
    my $users_bleats_dir = "$users_dir/$curr_user/bleats.txt";
    open (my $fh, '>>', $users_bleats_dir) or die "Could not open file $users_bleats_dir $!";
    print $fh "$new_bleat_id\n";
    close $fh;
    
}

#PRINTS THE CURRENT USERS NEWSFEED:
#shows the bleats of users they are listening to, and bleats that they are mentioned in
sub newsfeed {
    my ($user) = @_;
    $user =~ s/$users_dir\///;
    
    my $return_str = <<"eof";
    
    <div class="row">
    <div class="col s3 offset-s9">
            <form method="post"><label for="search"><i class="material-icons">search</i></label>
                     <input id="search" type="search" required name='bleat_search_query' placeholder="Search for bleats">
            </form>
        </div>
    <div class="container">
    <form method="post">
      <div class="row">
        <div class="input-field col s12">
          <textarea id="new_bleat_area" name='new_bleat_area' class="materialize-textarea" maxlength="142"></textarea>
          <label for="new_bleat_area">Type your bleat here</label>
            <button onclick = "alert_function()" class="btn waves-effect waves-light" type="submit" name="action">Post
    <i class="material-icons right">send</i>
  </button>
        <script>
        function alert_function () {
            alert("Bleat successful!");
        }
        </script>
        </div></div></form></div></div>
eof

    my %all_bleat_ids;
    my @listening = listening_array($user);
    push (@listening, $curr_user);
    foreach $person (@listening) {
        chomp $person;
        $person =~ s/$users_dir\///;
        my $users_bleats_dir = "$users_dir/$person/bleats.txt";
        open A, "<$users_bleats_dir" or die "can not open $users_bleats_dir: $!";
        foreach my $id (<A>) {
            $all_bleat_ids{$id} = $person;
        }
        close A;
    }

    my $bleats_str = "";
    foreach my $bleat_id (reverse sort keys %all_bleat_ids) {
        my $dir = "$bleats_dir/$bleat_id";
        open A, "<$dir" or die "can not open $dir: $!";
        my $bleat_text = "";
        foreach my $line (<A>) {
            if ($line =~ /^bleat/) {
                $bleat_text = $line;
                $bleat_text =~ s/^bleat: //;
                next;
            }
        }
        close A;
        my $action = "listen";
        my $input = "listen_user";
        my $tooltip = "Listen!";
        my $icon = "volume_up";
        if (is_listening($curr_user, $all_bleat_ids{$bleat_id}) eq 1) {
            $action = "unlisten";
            $input = "unlisten_user";
            $tooltip = "Unlisten.";
            $icon = "volume_off";
        } 

        my $pic = profile_pic($all_bleat_ids{$bleat_id}, "small");
        $bleats_str .= <<"eof"

    <div class="container">
        <div class="card-panel hoverable teal lighten-3 row">
            <div class="col s6">
                <h4>$pic <i>$all_bleat_ids{$bleat_id}</i></h4>
                $bleat_text
            </div>
            <div class="col s6">
                <div class="right-align">
                    <form>
                    <input type="hidden" name="$input" value=$all_bleat_ids{$bleat_id}>
                    <button type="submit" name="$action" class="btn-floating btn-large waves-effect waves-light teal tooltipped data-position="bottom" data-delay="50" data-tooltip="$tooltip"">
                    <i class="material-icons">$icon</i></button>
                    </form> <br>
                    <form>
                        <input type="hidden" name="in_reply_to" value=$bleat_id>
                    <button onclick="bleat_reply()" name="reply" data-target="modal1" class="btn-floating modal-trigger btn-large waves-effect waves-light teal tooltipped data-position="bottom" data-delay="50" data-tooltip="Reply!"">
<i class="material-icons">replay</i></button>

                    <input type="hidden" name="reply_text">

                    <script>
                    function bleat_reply() {
                        var reply = prompt("Please enter your reply.");
                        if (reply != null) {
                            document.getElementsByName("reply_text")[0].setAttribute("value", reply);
                        }
                    }
                    </script>
                    </form></div></div></div></div>
eof
    }

    return "$return_str$bleats_str";
}

## sub returns if USER 1 is listening to USER 2 (1=true, 0=false)
sub is_listening {
    my ($user1, $user2) = @_;
    my $dir = "$users_dir/$user1/details.txt";
    open A, "<$dir" or die "can not open $dir: $!";
    foreach my $line (<A>) {
        if ($line =~ /^listens/) {
            foreach (split (/ /, $line)) {
                (my $i = $_) =~ s/^\s*//;
                chomp $i;
                if ($i =~ /$user2/) { return 1; }
            }
            next;
        }
    }
    close A;
    return 0;
}

## makes user1 unfollow user2
sub make_unlisten {
    my ($user1, $user2) = @_;
    my $dir = "$users_dir/$user1/details.txt";
    my @details = ();
    open A, "<$dir"  or die "can not open $details_dir: $!";
    foreach my $line (<A>) {
        if ($line =~ /^listens/) {
            $line =~ s/$user2//;
            $line =~ s/  / /g;
        }
        push (@details, $line);
    }
    close A;
    open (my $fh, '>', $dir) or die "Could not open file $dir: $!";
	foreach my $line (@details) {
        print $fh $line;
    }
    close $fh;
}

## makes user 1 follow user2
sub make_listen {
    my ($user1, $user2) = @_;
    my $dir = "$users_dir/$user1/details.txt";
    my @details = ();
    open A, "<$dir"  or die "can not open $details_dir: $!";
    foreach my $line (<A>) {
        if ($line =~ /^listen/) {
            chomp $line;
            $line .= " $user2\n";
            $line =~ s/  / /g;
        }
        push (@details, $line);
    }
    close A;
    open (my $fh, '>', $dir) or die "Could not open file $dir: $!";
	foreach my $line (@details) {
        print $fh $line;
    }
    close $fh;
}

sub validate_pw {
    my ($username, $input_pw) = @_;
    my $user_dir = "$users_dir/$username";
    if ($username && $input_pw) {
        if ((-e $user_dir) && (-d $user_dir)) {
            $details_dir = "$user_dir/details.txt";
            open F, "<$details_dir" or die "can not open $details_dir: $!";
            my $correct_pw;
            foreach my $line (<F>) {
                if ($line =~ /^password/) {
                    $correct_pw = $line;
                    $correct_pw =~ s/^password: //;
                    next;
                }
            }
			
			if ($correct_pw =~ /$input_pw/) { return 1;
            } else { return "Password is incorrect."; }

            close F;
        } else {
            return "Username does not exist.";
        }
    } elsif ($username) {
        return "Please enter a password.";
    } elsif ($input_pw) {
        return "Please enter a username.";
    }
}

sub login_page {
    return <<eof                                                  
    <form action="bitter.cgi" method="post">
        <div class="container">
             <div class="card-panel teal lighten-2 hoverable"> 
              	 <div class="row">
                     <div class="input-field col s6">
                     <input id="username" type="text" name='username_field'>
                     <label for="username" style="color:black;">Username</label>
                 </div>
                     <div class="input-field col s6">
                     <input id="password" type="password" name='password_field'>
                     <label for="password" style="color:black;" >Password</label>
                     </div>
                 </div>
             </div>
      
            <button class="btn waves-effect waves-light center-align" type="submit" name="action">Login
                <i class="material-icons right">send</i>
            </button>
        </div>
    </form>
    
eof
}

##PRINTS SEARCH RESULTS
# where $query is a search query for bleats (substrings/keywords, hashtags)
sub bleat_search_results {
    my ($query) = @_;
    my @bleats = sort(glob("$bleats_dir/*"));
    my @results = ();
    my $results_str = "";
    foreach my $bleat_id (@bleats) {
        open A, "<$bleat_id" or die "can not open $details_dir: $!";
        my $bleat = "";
        my $username = "";
        foreach my $line (<A>) {
            if ($line =~ /^bleat/) {
                $bleat = $line;
                $bleat =~ s/^bleat: //;
            }
            if ($line =~ /^username/) {
                ($username = $line) =~ s/^username: //;
            }
        }
        close A;
        chomp $username;
        my $pic = profile_pic($username, "small");
        if ($bleat =~ /$query/i) {
            my $result = <<"eof";
         
        $pic
         <p class=\"flow-text\">
             <a href=\"bitter.cgi?user=$username&page=user\">
                <h3>\@$username</h3><br>
             </a>
             $bleat<br>
         </p>
eof

        $results_str .= "<br>\n<div class=\"card-panel teal lighten-3\">$result</div>";
        }
    }
    if ($results_str) {
        $results_str = "<h3>Results for <i>\"$query\"</i></h3>\n<div class=\"container\">\n$results_str\n</div>";
    } else {
        $results_str = "<h3>No results for <i>\"$query\"</i></h3>";
    }
    return $results_str;
}

##PRINTS SEARCH RESULTS
# where $query is a search query for usernames/fullnames
sub search_results {
    my ($query) = @_;
    my @users = sort(glob("$users_dir/*"));
    my $username = "";
    my $full_name = "";
    my @results = ();
    foreach my $user (@users) {
        my $details_dir = "$user/details.txt";
        open D, "<$details_dir" or die "can not open $details_dir: $!";
        foreach my $line (<D>) {
            if ($line =~ /^username/) {
                $username = $line;
                $username =~ s/^username: //;
            }
            if ($line =~ /^full_name/) {
                $full_name = $line;
                $full_name =~ s/^full_name: //;
            }
        }

        if (($username =~ /$query/i) || ($full_name =~ /$query/i)) {
            push(@results, $username);
        }
        close D;
    }
    $results_str = "";
    if ($#results > 0) {
        foreach my $line (@results) {
            #get full name
            chomp $line;
            my $details_dir = "$users_dir/$line/details.txt";
            open A, "<$details_dir" or die "can not open $details_dir: $!";
            my $full_name = "";
            foreach my $detail (<A>) {
                if ($detail =~ /^full_name/) {
                    $full_name = $detail;
                    $full_name =~ s/^full_name: //;
                }
            }
            close A;
            #get profile picture
            my $pic = profile_pic($line, "small");
            my $action = "listen";
            my $input = "search_listen";
            my $tooltip = "Listen!";
            my $icon = "volume_up";
            if (is_listening($curr_user, $line) eq 1) {
                $action = "unlisten";
                $input = "search_unlisten";
                $tooltip = "Unlisten.";
                $icon = "volume_off";
            } 
            my $result = <<"eof";
            
            <a href=\"bitter.cgi?user=$line&page=user\">
                <p class=\"flow-text\">
                    $pic
                    $full_name<br>
                    <font color=\"blue\">\@$line</font>
                 </p>
             </a>
             <div class="right-align">
                    <form>
                    <input type="hidden" name="$input" value="$line">
                    <input type="hidden" name="curr_search" value="$query">
                    <button type="submit" name="$action" class="btn-floating btn-large waves-effect waves-light teal tooltipped data-position="bottom" data-delay="50" data-tooltip="$tooltip"">
                    <i class="material-icons">$icon</i></button>
                    </form>
                </div>

eof

            $results_str .= "<br>\n<div class=\"card-panel teal lighten-3\">$result</div>";
        }
        $results_str = "<h3>Results for <i>\"$query\"</i></h3>\n<div class=\"container\">\n$results_str\n</div>";
    } else {
        $results_str = "<h3>No results for <i>\"$query\"</i></h3>";
    }
	
    return $results_str;
}

sub listening_array {
    my ($user) = @_;
    my $details_dir = "$users_dir/$user/details.txt";
    open A, "<$details_dir" or die "can not open $details_dir: $!";
    foreach my $line (<A>) {
        if ($line =~ /^listens/) {
            $line =~ s/^listens:\s*//;
            return split(/\s+/, $line);
        }
    }
    close A;
}

sub print_listening {
    my ($user_to_test) = @_;
    my @users = listening_array($user_to_test);
    my $listening_str = "";
    foreach my $user (@users) {
        my $pic = profile_pic($user, "small");
        $listening_str .= "$pic<a href=\"bitter.cgi?page=user&user=$user\">\@$user</a><br>\n";
    }
    return "<h5>Listens to:</h5>$listening_str";
}

sub print_details {
	my ($user) = @_;
    $user =~ s/$users_dir\///g;
    my $details_filename = "$users_dir/$user/details.txt";
    open E, "<$details_filename" or die "can not open $details_filename: $!";
    
    %details;
    foreach my $line (<E>) {
        if ($line !~ /^\s*(email|password)/) {
            if ($line =~ /([\w _]*):(.*)/) {
                $details{$1} = $2;
            }
        }
    }
    my $username = "<h4 class=\"truncate\">$details{username}</h4>";
    my $details_string = "";
    my @order = ("full_name", "home_latitude", "home_longitude", "home_suburb");
    foreach $key (@order) {
        if (exists $details{$key}) {
			($new_key = $key) =~ s/_/ /g;
			$new_key =~ s/(full |home )//;
			if ($new_key =~ /^([a-z])/) {
				my $first_letter = $1;
				my $upper = uc $first_letter;
				$new_key =~ s/^$first_letter/$upper/;
			}
            $details_string .= "<b>$new_key:</b> $details{$key}<br>";
       }
    }
    close E;
    $user =~ s/^dataset-$dataset_size\/users\///;
    my $listening_str = print_listening($user);
	return "$username$details_string<br>$listening_str";
}

sub profile_pic {
	my ($user, $size) = @_;
    $user =~ s/$users_dir\///g;
    $image_dir = "$users_dir/$user/profile.jpg";
    my $image = "";
    if (! -e $image_dir) {
        $image_dir = "default.jpg";
    }
    my $name = $user;
    $name =~ s/$users_dir\///;
    if ($size eq "small") {
            $image = "<a href=bitter.cgi?page=user&user=$name><img src=\"$image_dir\" alt=\"Profile Picture\" class=\"circle responsive-img\" style=\"width:50px;height:50px;\"></a>";
        } elsif ($size eq "large") {
            $image = "<a href=bitter.cgi?page=user&user=$name><div class=\"center-align\"><img src=\"$image_dir\" alt=\"Profile Picture\" class=\"circle responsive-img\"></div></a>";
        }
	return $image;
}

sub print_bleats {
    my ($user) = @_;
    $user =~ s/$users_dir\///g;
    my $bleats_filename = "$users_dir/$user/bleats.txt";
    open F, "<$bleats_filename" or die "can not open $bleats_filename: $!";
    
    #my $bleats = "<h3 class=\"center-align\">Bleats</h3>";
    my $bleats = "";
    my @array = ();
    foreach my $bleat_id (<F>) {
        push (@array, $bleat_id);
    }
    foreach my $bleat_id (reverse @array) {
        my $path = "$bleats_dir/$bleat_id";
        open G, "<$path" or die "cannot open $path: $!";
        foreach my $line (<G>) {
            if ($line =~ /^\s*bleat/i) {
                $line =~ s/^\s*bleat:\s*//i;
                chomp $line;
                my $name = $user;
                $name =~ s/$users_dir\///;
                $bleats .= "<div class=\"card-panel hoverable teal lighten-3\">\n<h4><i>$name</i></h4>$line";

                if ($user eq $curr_user) {
                    $bleats .= <<"eof";
                    <form>
                    <div class = "row">
                    <input type="hidden" name="delete_bleat" value=$bleat_id>
                    <button type="submit" name="delete" class="btn-floating btn-large waves-effect waves-light teal tooltipped data-position="bottom" data-delay="50" data-tooltip="Delete bleat"">
                    <i class="material-icons">delete</i></button>
                    </div>
                </form> 
eof
                }
                $bleats .= "</div>";  
            }
        }
    }
    close F;
	return $bleats;
}

###########################################################

#
# Show unformatted details for user "n".
# Increment parameter n and store it as a hidden variable
#
sub user_page {
    my ($user_to_show) = @_;    
    $user_to_show =~ s/$users_dir\///g;
    my $image = profile_pic($user_to_show, "large");
    my $bleats = print_bleats($user_to_show);
    my $details = print_details($user_to_show);
    

    my $action = "listen";
    my $input = "userpage_listen";
    my $tooltip = "Listen!";
    my $icon = "volume_up";
    my $message = "Listen";
    if (is_listening($curr_user, $user_to_show) eq 1) {
        $action = "unlisten";
        $input = "userpage_unlisten";
        $tooltip = "Unlisten.";
        $icon = "volume_off";
        $message = "unlisten";
    } 

    return <<eof

<br>
<div class="container">
<div class="row">
    <div class="col s4">
        <div class="card-panel teal lighten-2">
            $image<br>
                <form>
                <input type="hidden" name="$input" value=$user_to_show>
                <button type="submit" name="$action" class="waves-effect waves-light btn teal tooltipped data-position="bottom" data-delay="50" data-tooltip="$tooltip"">
                <i class="material-icons right">$icon</i>$message</button>
                </form>
            <br>$details
        </div>
    </div>
    <div class="col s8">
            $bleats
        <br>
    </div>
</div>
</div>
eof
}

sub nav_bar {
my ($logged_out, $user) = @_;

my $return_string = <<"eof";
<nav class="teal lighten-2">
  <div class="nav-wrapper">
    <a href="#!" class="brand-logo center"><b>Bitter</b></a>
    <ul class="right hide-on-med-and-down">

eof

if ($logged_out eq 0) {
    $return_string .= <<"eof"

    <li><a href="bitter.cgi?user=$user&page=home"><b>Home</b></a></li>
    <li><a href="bitter.cgi?user=$user&page=user"><b>My Profile: </b>$user</a></li>
    <li><a href=\"bitter.cgi?logging_out=1\">Logout</a></li>
        </ul>
            <ul id="nav-mobile" class="left hide-on-med-and-down">
                    <form method="post">
                    <div class="input-field">
                         <input id="search" type="search" required name='search_query' placeholder="Search for users">
                        <label for="search"><i class="material-icons">search</i></label>
                        <i class="material-icons">close</i>
                    </div>
                </form>
                </ul>       
eof
}
$return_string .= "</div>\n</nav>";

return $return_string;

}

#
# HTML placed at the top of every page
#
sub page_header {
    if ($cookie) {
        print "Set-Cookie: $cookie";
    }

    return <<eof
Content-Type: text/html

<!DOCTYPE html>
<html lang="en">
<head>
<title>Bitter</title>
<link href="bitter.css" rel="stylesheet">
<link href="materialize/css/materialize.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
<script src="materialize/js/materialize.js"></script>
</head>
<body>
  <!-- jQuery is required by Materialize to function -->
  <script type="text/javascript" src="https://code.jquery.com/jquery-2.1.1.min.js"></script>
  <script type="text/javascript" src="js/materialize.min.js"></script>
  <script type="text/javascript">
    //custom JS code
  </script>
eof
}


#
# HTML placed at the bottom of every page
# It includes all supplied parameter values as a HTML comment
# if global variable $debug is set
#
sub page_trailer {
    my $html = "";
    $html .= join("", map("<!-- $_=".param($_)." -->\n", param())) if $debug;
    $html .= end_html;
    return $html;
}

main();
